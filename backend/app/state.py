"""Global in-process state — auth, active device, live stream sessions."""

import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock

import httpx

from tablo_api import TabloAuth, TabloClient
from tablo_api.models import TabloDevice, TabloChannel, TabloStream

CONFIG_PATH = Path("/data/config.json")

_lock = Lock()


class StreamSession:
    """Tracks a live HLS stream for one viewer."""

    def __init__(self, stream: TabloStream, base_url: str) -> None:
        self.stream = stream
        # base URL of the Tablo device (e.g. http://10.0.0.5:8885)
        self.base_url = base_url


class AppState:
    def __init__(self) -> None:
        self.auth: TabloAuth | None = None
        self.email: str | None = None
        self.devices: list[TabloDevice] = []
        self.active_device: TabloDevice | None = None
        self._channels: list[TabloChannel] | None = None
        self.streams: dict[str, StreamSession] = {}  # session_id → session
        self._http = httpx.AsyncClient(timeout=30)
        # Grid enrichment cache — avoids re-fetching 800 airing details on every guide load
        self._grid_cache: tuple | None = None
        self._grid_cache_time: float = 0.0
        self._grid_cache_lock = asyncio.Lock()

    _GRID_CACHE_TTL = 600  # seconds — 10 minutes

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load_config(self) -> None:
        if not CONFIG_PATH.exists():
            return
        try:
            cfg = json.loads(CONFIG_PATH.read_text())
            email = cfg.get("email")
            password = cfg.get("password")
            if email and password:
                self.auth = TabloAuth(email, password)
                self.email = email
        except Exception:
            pass

    def save_config(self, email: str, password: str) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps({"email": email, "password": password}))

    def clear_config(self) -> None:
        if CONFIG_PATH.exists():
            CONFIG_PATH.unlink()
        self.auth = None
        self.email = None
        self.devices = []
        self.active_device = None
        self._channels = None
        self.streams.clear()

    # ------------------------------------------------------------------
    # Auth / discovery
    # ------------------------------------------------------------------

    async def login(self, email: str, password: str) -> list[TabloDevice]:
        auth = TabloAuth(email, password)
        devices = await _run_sync(auth.discover)
        self.auth = auth
        self.email = email
        self.devices = devices
        self.active_device = devices[0] if len(devices) == 1 else None
        self._channels = None
        self.save_config(email, password)
        return devices

    async def select_device(self, sid: str) -> TabloDevice:
        dev = next((d for d in self.devices if d.sid == sid), None)
        if dev is None:
            raise ValueError(f"Device {sid} not found")
        self.active_device = dev
        self._channels = None
        return dev

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------

    async def channels(self, refresh: bool = False, include_ott: bool = True) -> list[TabloChannel]:
        """Get channels from Tablo (OTA + OTT)."""
        if self.active_device is None:
            raise RuntimeError("No active device")

        if self._channels is None or refresh:
            client = TabloClient(self.active_device)

            # Ultra-safe wrapper
            def fetch_channels():
                try:
                    return client.channels(include_ott=include_ott)
                except Exception as e:
                    print(f"Error calling client.channels: {e}")
                    raise

            self._channels = await _run_sync(fetch_channels)

        return self._channels


    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def start_stream(self, identifier: str) -> tuple[str, StreamSession]:
        if self.active_device is None:
            raise RuntimeError("No active device")
        client = TabloClient(self.active_device)
        stream = await _run_sync(client.watch, identifier)
        session_id = uuid.uuid4().hex

        # Deriving base_url from the playlist_url ensures we use the correct port
        # for segments and nested playlists (e.g. port 80 vs 8887).
        from urllib.parse import urlparse
        parsed = urlparse(stream.playlist_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        sess = StreamSession(stream=stream, base_url=base_url)
        with _lock:
            self.streams[session_id] = sess
        return session_id, sess

    def get_session(self, session_id: str) -> StreamSession | None:
        return self.streams.get(session_id)

    async def request_device(self, method: str, path: str, body: str = "") -> dict:
        """Make an authenticated request to the active local Tablo device."""
        if self.active_device is None:
            raise RuntimeError("No active device")
        
        from tablo_api import TabloAuth
        auth_header, date_header = TabloAuth.make_device_auth(method, path, body)
        
        url = self.active_device.local_url.rstrip("/") + path
        resp = await self._http.request(
            method,
            url,
            content=body.encode() if body else None,
            headers={
                "Authorization": auth_header,
                "Date": date_header,
                "User-Agent": "Tablo-FAST/1.7.0 (Mobile; iPhone; iOS 18.4)",
            }
        )
        resp.raise_for_status()
        return resp.json()

    def _cloud_headers(self) -> tuple[str, dict]:
        """Return (cloud_base_url, auth_headers) for the active device."""
        dev = self.active_device
        return "https://lighthousetv.ewscloud.com", {
            "Authorization": f"Bearer {dev.account_token}",
            "Lighthouse": dev.lighthouse_token,
            "User-Agent": "Tablo-FAST/2.0.0 (Mobile; iPhone; iOS 16.6)",
        }

    async def _fetch_cloud_channels(self) -> tuple[dict, list[str]]:
        """Fetch OTT channel list from the cloud API (single request, fast).

        Returns (logo_map, identifiers).
        """
        if self.active_device is None:
            return {}, []
        host, headers = self._cloud_headers()
        try:
            resp = await self._http.get(
                f"{host}/api/v2/account/{self.active_device.lighthouse_token}/guide/channels/",
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            channels = resp.json()
        except Exception:
            return {}, []

        logo_map: dict = {}
        identifiers: list[str] = []
        for ch in channels:
            identifier = ch.get("identifier")
            if not identifier:
                continue
            identifiers.append(identifier)
            logos = ch.get("logos") or []
            logo = next((lg["url"] for lg in logos if lg.get("kind") == "originalLarge"), None)
            if not logo:
                logo = next((lg["url"] for lg in logos if lg.get("kind") == "lightLarge"), None)
            if not logo:
                logo = next((lg.get("url") for lg in logos if lg.get("url")), None)
            if logo:
                logo_map[identifier] = logo

        return logo_map, identifiers

    async def _fetch_cloud_airings(self, identifiers: list[str]) -> dict:
        """Fetch current airing for each OTT channel identifier (parallel, semaphore-limited).

        Returns airing_map keyed by identifier.
        """
        if self.active_device is None or not identifiers:
            return {}
        host, headers = self._cloud_headers()
        token = self.active_device.lighthouse_token
        sem = asyncio.Semaphore(20)

        async def fetch_one(ident: str):
            async with sem:
                try:
                    r = await self._http.get(
                        f"{host}/api/v2/account/{token}/guide/channels/{ident}/airings/",
                        headers=headers,
                        timeout=10,
                    )
                    if r.status_code == 200:
                        items = r.json()
                        if isinstance(items, list) and items:
                            a = items[0]
                            return ident, {
                                "title": a.get("title") or a.get("show", {}).get("title"),
                                "description": a.get("description"),
                                "start": a.get("datetime"),
                                "duration": a.get("duration"),
                                "genres": a.get("genres") or [],
                                "kind": a.get("kind"),
                            }
                except Exception:
                    pass
                return ident, None

        results = await asyncio.gather(*[fetch_one(i) for i in identifiers])
        return {ident: data for ident, data in results if data is not None}

    async def _fetch_cloud_data(self) -> tuple[dict, dict]:
        """Fetch OTT channel logos and current airings from the Tablo cloud API.

        Returns (logo_map, airing_map) both keyed by channel identifier.
        """
        logo_map, identifiers = await self._fetch_cloud_channels()
        airing_map = await self._fetch_cloud_airings(identifiers)
        return logo_map, airing_map

    async def _fetch_guide_enrichment_local(self) -> tuple[dict, dict, dict]:
        """Fetch local device logos and current airings (OTA only).

        Returns (logo_map, path_to_ident, channel_airing_map).
        """
        path_results = await asyncio.gather(
            self.request_device("GET", "/guide/channels"),
            self.request_device("GET", "/guide/airings"),
            return_exceptions=True,
        )
        detail_paths = path_results[0] if not isinstance(path_results[0], Exception) else []
        airing_paths = path_results[1] if not isinstance(path_results[1], Exception) else []

        sem = asyncio.Semaphore(30)

        async def fetch_detail(path):
            async with sem:
                try:
                    return path, await self.request_device("GET", path)
                except Exception:
                    return path, None

        async def fetch_airing(path):
            async with sem:
                try:
                    return await self.request_device("GET", path)
                except Exception:
                    return None

        detail_results, airing_results = await asyncio.gather(
            asyncio.gather(*[fetch_detail(p) for p in detail_paths[:300]]),
            asyncio.gather(*[fetch_airing(p) for p in airing_paths[:800]]),
        )

        logo_map: dict = {}
        path_to_ident: dict = {}
        for path, d in detail_results:
            if d and "channel" in d:
                c_info = d["channel"]
                ident = c_info.get("channel_identifier")
                path_to_ident[d.get("path", path)] = ident
                logos = c_info.get("logos", [])
                logo = next(( logo["url"] for logo in logos if logo["kind"] == "originalLarge"), None)
                if not logo:
                    logo = next(( logo["url"] for logo in logos if logo["kind"] == "lightLarge"), None)
                if ident and logo:
                    logo_map[ident] = logo

        now = datetime.now(timezone.utc)
        channel_airing_map: dict = {}
        for a in airing_results:
            if not a or "airing_details" not in a:
                continue
            ad = a["airing_details"]
            try:
                start_str = ad.get("datetime")
                if not start_str:
                    continue
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                duration = ad.get("duration", 0)
                end = start + timedelta(seconds=duration)
                if start <= now < end:
                    c_path = ad.get("channel_path")
                    if c_path:
                        channel_airing_map[c_path] = {
                            "title": ad.get("show_title"),
                            "description": a.get("episode", {}).get("description") or a.get("series", {}).get("description"),
                            "start": start_str,
                            "duration": duration,
                            "genres": ad.get("genres") or [],
                            "kind": ad.get("event_type"),
                        }
            except Exception:
                continue

        return logo_map, path_to_ident, channel_airing_map

    async def _fetch_guide_enrichment(self) -> tuple[dict, dict, dict, dict]:
        """Fetch logo and airing data from local device and cloud in parallel.

        Returns (logo_map, path_to_ident, channel_airing_map, cloud_airing_map).
        channel_airing_map is keyed by local channel path (OTA only).
        cloud_airing_map is keyed by channel identifier (OTT).
        """
        path_results = await asyncio.gather(
            self.request_device("GET", "/guide/channels"),
            self.request_device("GET", "/guide/airings"),
            self._fetch_cloud_data(),
            return_exceptions=True,
        )
        detail_paths = path_results[0] if not isinstance(path_results[0], Exception) else []
        airing_paths = path_results[1] if not isinstance(path_results[1], Exception) else []
        cloud_logos: dict
        cloud_airing_map: dict
        if isinstance(path_results[2], Exception):
            cloud_logos, cloud_airing_map = {}, {}
        else:
            cloud_logos, cloud_airing_map = path_results[2]

        sem = asyncio.Semaphore(30)

        async def fetch_detail(path):
            async with sem:
                try:
                    return path, await self.request_device("GET", path)
                except Exception:
                    return path, None

        async def fetch_airing(path):
            async with sem:
                try:
                    return await self.request_device("GET", path)
                except Exception:
                    return None

        detail_results, airing_results = await asyncio.gather(
            asyncio.gather(*[fetch_detail(p) for p in detail_paths[:300]]),
            asyncio.gather(*[fetch_airing(p) for p in airing_paths[:800]]),
        )

        logo_map: dict = {}
        path_to_ident: dict = {}
        for path, d in detail_results:
            if d and "channel" in d:
                c_info = d["channel"]
                ident = c_info.get("channel_identifier")
                path_to_ident[d.get("path", path)] = ident
                logos = c_info.get("logos", [])
                logo = next(( logo["url"] for logo in logos if logo["kind"] == "originalLarge"), None)
                if not logo:
                    logo = next(( logo["url"] for logo in logos if logo["kind"] == "lightLarge"), None)
                if ident and logo:
                    logo_map[ident] = logo

        now = datetime.now(timezone.utc)
        channel_airing_map: dict = {}
        for a in airing_results:
            if not a or "airing_details" not in a:
                continue
            ad = a["airing_details"]
            try:
                start_str = ad.get("datetime")
                if not start_str:
                    continue
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                duration = ad.get("duration", 0)
                end = start + timedelta(seconds=duration)
                if start <= now < end:
                    c_path = ad.get("channel_path")
                    if c_path:
                        channel_airing_map[c_path] = {
                            "title": ad.get("show_title"),
                            "description": a.get("episode", {}).get("description") or a.get("series", {}).get("description"),
                            "start": start_str,
                            "duration": duration,
                            "genres": ad.get("genres") or [],
                            "kind": ad.get("event_type"),
                        }
            except Exception:
                continue

        # Merge cloud logos as fallback (local logos take priority)
        for ident, url in cloud_logos.items():
            if ident not in logo_map:
                logo_map[ident] = url

        return logo_map, path_to_ident, channel_airing_map, cloud_airing_map

    async def get_guide_data(self) -> list[dict]:
        """Aggregate channels with logos and current airing info."""
        if self.active_device is None:
            raise RuntimeError("No active device")

        channels = await self.channels()
        logo_map, path_to_ident, channel_airing_map, cloud_airing_map = await self._fetch_guide_enrichment()

        guide = []
        for c in channels:
            c_path = next((p for p, ident in path_to_ident.items() if ident == c.identifier), None)
            current_program = (channel_airing_map.get(c_path) if c_path else None) or cloud_airing_map.get(c.identifier)
            guide.append({
                "identifier": c.identifier,
                "call_sign": c.call_sign,
                "major": c.major,
                "minor": c.minor,
                "network": c.network,
                "kind": c.kind,
                "display_name": c.display_name,
                "logo_url": logo_map.get(c.identifier),
                "current_program": current_program,
            })

        return guide

    async def stream_guide_data(self):
        """Async generator for NDJSON guide streaming.

        Yields basic channel records immediately, then enriched records once
        logo/airing data is available. The frontend merges by identifier.
        """
        if self.active_device is None:
            raise RuntimeError("No active device")

        channels = await self.channels()

        def _stub(c, logo_url=None, current_program=None):
            return json.dumps({
                "identifier": c.identifier,
                "call_sign": c.call_sign,
                "major": c.major,
                "minor": c.minor,
                "network": c.network,
                "kind": c.kind,
                "display_name": c.display_name,
                "logo_url": logo_url,
                "current_program": current_program,
            }) + "\n"

        # Phase 1: bare stubs so the UI renders immediately on cold start.
        # Skip when cache is warm — Phase 3 will be instant and stubs would
        # briefly clobber existing logo/program data already held by the frontend.
        import time as _time
        cache_warm = bool(
            self._grid_cache and _time.monotonic() - self._grid_cache_time < self._GRID_CACHE_TTL
        )
        if not cache_warm:
            for c in channels:
                yield _stub(c)

        # Phase 2: cloud logos fast path — only when enrichment cache is cold
        if not cache_warm:
            cloud_logo_map, _ = await self._fetch_cloud_channels()
            for c in channels:
                if c.identifier in cloud_logo_map:
                    yield _stub(c, logo_url=cloud_logo_map[c.identifier])

        # Phase 3: full enrichment via shared grid cache (instant on hit, ~90s on cold start)
        try:
            logo_map, path_to_ident, channel_to_airings, cloud_airing_map = await asyncio.wait_for(
                self._build_grid_enrichment(), timeout=90
            )
        except Exception as e:
            print(f"[guide-live] Phase 3 failed: {type(e).__name__}: {e}")
            return

        now = datetime.now(timezone.utc)

        def _current_airing(airings: list) -> dict | None:
            for air in airings:
                start_str = air.get("start")
                if not start_str:
                    continue
                try:
                    start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    end = start + timedelta(seconds=air.get("duration") or 0)
                    if start <= now < end:
                        return air
                except Exception:
                    pass
            return None

        for c in channels:
            c_path = next((p for p, ident in path_to_ident.items() if ident == c.identifier), None)
            airings = channel_to_airings.get(c_path, []) if c_path else []
            current_program = _current_airing(airings) or cloud_airing_map.get(c.identifier)
            yield _stub(c, logo_url=logo_map.get(c.identifier), current_program=current_program)

    async def get_recordings(self) -> list[dict]:
        """Fetch all recordings from the device."""
        if self.active_device is None:
            raise RuntimeError("No active device")

        import asyncio
        try:
            paths = await self.request_device("GET", "/recordings/airings")
        except Exception:
            return []

        async def fetch_recording(path):
            try:
                data = await self.request_device("GET", path)
                # Enriched with some helpful fields
                ad = data.get("airing_details", {})
                return {
                    "identifier": data.get("object_id"),
                    "path": path,
                    "title": ad.get("show_title"),
                    "description": data.get("episode", {}).get("description") or data.get("series", {}).get("description"),
                    "start": ad.get("datetime"),
                    "duration": ad.get("duration"),
                    "thumbnail": None # Could resolve series image later
                }
            except Exception:
                return None

        # Fetch first 50 recordings for now to keep it snappy
        recordings = await asyncio.gather(*[fetch_recording(p) for p in paths[:50]])
        return [r for r in recordings if r]

    async def _build_grid_enrichment(self, max_airings: int = 1000) -> tuple[dict, dict, dict, dict]:
        """Fetch logos and airings for the grid guide.

        Returns (logo_map, path_to_ident, channel_to_airings, cloud_airing_map).
        Results are cached for _GRID_CACHE_TTL seconds so repeated guide loads
        don't re-fetch hundreds of airing detail records from the device.
        The EPG endpoint passes max_airings=15000 and bypasses the cache.
        """
        import time as _time

        # Cache only applies to the standard guide load (max_airings == 1000)
        use_cache = max_airings == 1000
        if use_cache:
            async with self._grid_cache_lock:
                if self._grid_cache and _time.monotonic() - self._grid_cache_time < self._GRID_CACHE_TTL:
                    return self._grid_cache

        path_results = await asyncio.gather(
            self.request_device("GET", "/guide/channels"),
            self.request_device("GET", "/guide/airings"),
            self._fetch_cloud_data(),
            return_exceptions=True,
        )
        local_paths = path_results[0] if not isinstance(path_results[0], Exception) else []
        airing_paths = path_results[1] if not isinstance(path_results[1], Exception) else []
        cloud_logos: dict
        cloud_airing_map: dict
        if isinstance(path_results[2], Exception):
            cloud_logos, cloud_airing_map = {}, {}
        else:
            cloud_logos, cloud_airing_map = path_results[2]

        sem = asyncio.Semaphore(30)

        async def fetch_detail(path):
            async with sem:
                try:
                    return await self.request_device("GET", path)
                except Exception:
                    return None

        async def fetch_airing(path):
            async with sem:
                try:
                    return await self.request_device("GET", path)
                except Exception:
                    return None

        details, airing_details = await asyncio.gather(
            asyncio.gather(*[fetch_detail(p) for p in local_paths[:300]]),
            asyncio.gather(*[fetch_airing(p) for p in airing_paths[:max_airings]]),
        )

        path_to_ident: dict = {}
        logo_map: dict = {}
        for d in details:
            if d and "channel" in d:
                c_info = d["channel"]
                ident = c_info.get("channel_identifier")
                path_to_ident[d["path"]] = ident
                logos = c_info.get("logos", [])
                logo = next(( logo["url"] for logo in logos if logo["kind"] == "originalLarge"), None)
                if not logo:
                    logo = next(( logo["url"] for logo in logos if logo["kind"] == "lightLarge"), None)
                if ident and logo:
                    logo_map[ident] = logo

        for ident, url in cloud_logos.items():
            if ident not in logo_map:
                logo_map[ident] = url

        cloud_airing_map_local = cloud_airing_map  # rename for closure clarity
        channel_to_airings: dict = {}
        for a in airing_details:
            if not a or "airing_details" not in a:
                continue
            ad = a["airing_details"]
            c_path = ad.get("channel_path")
            if not c_path:
                continue
            channel_to_airings.setdefault(c_path, []).append({
                "title": ad.get("show_title"),
                "description": a.get("episode", {}).get("description") or a.get("series", {}).get("description"),
                "start": ad.get("datetime"),
                "duration": ad.get("duration"),
                "genres": ad.get("genres") or [],
                "kind": ad.get("event_type"),
            })

        result = logo_map, path_to_ident, channel_to_airings, cloud_airing_map_local
        if use_cache:
            async with self._grid_cache_lock:
                self._grid_cache = result
                self._grid_cache_time = _time.monotonic()
        return result

    def _assemble_grid_row(self, c, logo_map: dict, path_to_ident: dict, channel_to_airings: dict, cloud_airing_map: dict) -> dict:
        c_path = next((p for p, ident in path_to_ident.items() if ident == c.identifier), None)
        airings = channel_to_airings.get(c_path, []) if c_path else []
        # For OTT channels with no local airings, inject cloud current program
        if not airings and c.identifier in cloud_airing_map:
            airings = [cloud_airing_map[c.identifier]]
        airings.sort(key=lambda x: x.get("start") or "")
        return {
            "identifier": c.identifier,
            "call_sign": c.call_sign,
            "major": c.major,
            "minor": c.minor,
            "network": c.network,
            "display_name": c.display_name,
            "logo_url": logo_map.get(c.identifier),
            "airings": airings,
        }

    async def get_grid_guide(self) -> list[dict]:
        """Fetch a traditional grid guide (channels + multiple upcoming airings)."""
        if self.active_device is None:
            raise RuntimeError("No active device")
        channels = await self.channels()
        logo_map, path_to_ident, channel_to_airings, cloud_airing_map = await self._build_grid_enrichment()
        return [self._assemble_grid_row(c, logo_map, path_to_ident, channel_to_airings, cloud_airing_map) for c in channels]

    async def get_epg_guide(self) -> list[dict]:
        """Full multi-day guide fetch for XMLTV EPG — fetches up to 15000 airings."""
        if self.active_device is None:
            raise RuntimeError("No active device")
        channels = await self.channels()
        logo_map, path_to_ident, channel_to_airings, cloud_airing_map = await self._build_grid_enrichment(max_airings=15000)
        return [self._assemble_grid_row(c, logo_map, path_to_ident, channel_to_airings, cloud_airing_map) for c in channels]

    async def stream_grid_guide_data(self):
        """Async generator for NDJSON grid guide streaming.

        Phase 1: emits channel stubs immediately so the grid renders at once.
        Phase 2: emits fully-enriched rows (logos + airings) once fetching is done.
        """
        if self.active_device is None:
            raise RuntimeError("No active device")

        channels = await self.channels()

        # Phase 1: channel stubs — grid rows appear immediately
        for c in channels:
            yield json.dumps({
                "identifier": c.identifier,
                "call_sign": c.call_sign,
                "major": c.major,
                "minor": c.minor,
                "network": c.network,
                "display_name": c.display_name,
                "logo_url": None,
                "airings": [],
            }) + "\n"

        # Phase 2: enriched rows with logos and timelines (90s hard timeout)
        try:
            logo_map, path_to_ident, channel_to_airings, cloud_airing_map = await asyncio.wait_for(
                self._build_grid_enrichment(), timeout=90
            )
        except Exception as e:
            print(f"[guide-grid] Phase 2 failed: {type(e).__name__}: {e}")
            return
        for c in channels:
            yield json.dumps(self._assemble_grid_row(c, logo_map, path_to_ident, channel_to_airings, cloud_airing_map)) + "\n"

    def stop_session(self, session_id: str) -> None:
        with _lock:
            self.streams.pop(session_id, None)

    @property
    def is_authenticated(self) -> bool:
        return self.auth is not None

    @property
    def http(self) -> httpx.AsyncClient:
        return self._http


# Module-level singleton
state = AppState()


async def _run_sync(fn, *args):
    """Run a blocking function in the default thread pool."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn, *args)
