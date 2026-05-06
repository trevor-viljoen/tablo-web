"""Global in-process state — auth, active device, live stream sessions."""

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
        self.devices: list[TabloDevice] = []
        self.active_device: TabloDevice | None = None
        self._channels: list[TabloChannel] | None = None
        self.streams: dict[str, StreamSession] = {}  # session_id → session
        self._http = httpx.AsyncClient(timeout=30)

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
        except Exception:
            pass

    def save_config(self, email: str, password: str) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps({"email": email, "password": password}))

    def clear_config(self) -> None:
        if CONFIG_PATH.exists():
            CONFIG_PATH.unlink()
        self.auth = None
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
        sess = StreamSession(stream=stream, base_url=self.active_device.local_url.rstrip("/"))
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

    async def get_guide_data(self) -> list[dict]:
        """Aggregate channels with logos and current airing info."""
        if self.active_device is None:
            raise RuntimeError("No active device")

        import asyncio

        # 1. Get base channels (cloud)
        channels = await self.channels()
        
        # 2. Get local channel detail paths
        try:
            local_paths = await self.request_device("GET", "/guide/channels")
        except Exception:
            local_paths = []

        # 3. Fetch channel details in parallel (limit to first 300 for safety)
        sem = asyncio.Semaphore(30)
        async def fetch_detail(path):
            async with sem:
                try:
                    return await self.request_device("GET", path)
                except Exception:
                    return None

        details = await asyncio.gather(*[fetch_detail(p) for p in local_paths[:300]])
        
        # Map channel_identifier -> logo_url
        logo_map = {}
        for d in details:
            if d and "channel" in d:
                c_info = d["channel"]
                ident = c_info.get("channel_identifier")
                logos = c_info.get("logos", [])
                # Prefer originalLarge, then lightLarge
                logo = next((logo_entry["url"] for logo_entry in logos if logo_entry["kind"] == "originalLarge"), None)
                if not logo:
                    logo = next((logo_entry["url"] for logo_entry in logos if logo_entry["kind"] == "lightLarge"), None)
                if ident and logo:
                    logo_map[ident] = logo

        # 4. Get current airings
        try:
            airing_paths = await self.request_device("GET", "/guide/airings")
        except Exception:
            airing_paths = []

        # We'll fetch a larger number of airings to cover OTA and OTT channels.
        # Tablo Gen 4 can have 100+ FAST channels.
        sem = asyncio.Semaphore(30)
        async def fetch_airing(path):
            async with sem:
                try:
                    return await self.request_device("GET", path)
                except Exception:
                    return None

        # Increase limit to 800 to cover more channels (especially OTT)
        airing_details = await asyncio.gather(*[fetch_airing(p) for p in airing_paths[:800]])
        
        # Map channel_path -> current_airing
        channel_airing_map = {}
        now = datetime.now(timezone.utc)
        
        for a in airing_details:
            if not a or "airing_details" not in a:
                continue
            
            ad = a["airing_details"]
            try:
                start_str = ad.get("datetime")
                if not start_str:
                    continue
                
                # Parse ISO date (e.g. 2026-05-06T11:00Z)
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                duration = ad.get("duration", 0)
                end = start + timedelta(seconds=duration)
                
                if start <= now < end:
                    c_path = ad.get("channel_path")
                    if c_path:
                        # Store show info
                        channel_airing_map[c_path] = {
                            "title": ad.get("show_title"),
                            "description": a.get("episode", {}).get("description") or a.get("series", {}).get("description"),
                            "start": start_str,
                            "duration": duration
                        }
            except Exception:
                continue

        # 5. Build final guide
        # We need to link channel identifiers back to paths.
        # Let's rebuild the map more carefully.
        path_to_ident = {}
        for d in details:
            if d and "channel" in d:
                path_to_ident[d["path"]] = d["channel"]["channel_identifier"]

        guide = []
        for c in channels:
            # Find the path for this channel to get its airing
            c_path = next((path for path, ident in path_to_ident.items() if ident == c.identifier), None)
            
            guide.append({
                "identifier": c.identifier,
                "call_sign": c.call_sign,
                "major": c.major,
                "minor": c.minor,
                "network": c.network,
                "kind": c.kind,
                "display_name": c.display_name,
                "logo_url": logo_map.get(c.identifier),
                "current_program": channel_airing_map.get(c_path) if c_path else None
            })
            
        return guide

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

    async def get_grid_guide(self) -> list[dict]:
        """Fetch a traditional grid guide (channels + multiple upcoming airings)."""
        if self.active_device is None:
            raise RuntimeError("No active device")

        import asyncio

        # 1. Get base channels
        channels = await self.channels()
        
        # 2. Get local channel detail paths to map identifier -> path
        try:
            local_paths = await self.request_device("GET", "/guide/channels")
        except Exception:
            local_paths = []

        sem = asyncio.Semaphore(30)
        async def fetch_detail(path):
            async with sem:
                try:
                    return await self.request_device("GET", path)
                except Exception:
                    return None

        details = await asyncio.gather(*[fetch_detail(p) for p in local_paths[:300]])
        path_to_ident = {}
        logo_map = {}
        for d in details:
            if d and "channel" in d:
                c_info = d["channel"]
                ident = c_info.get("channel_identifier")
                path_to_ident[d["path"]] = ident
                logos = c_info.get("logos", [])
                logo = next((logo_entry["url"] for logo_entry in logos if logo_entry["kind"] == "originalLarge"), None)
                if ident and logo:
                    logo_map[ident] = logo

        # 3. Get airings
        try:
            airing_paths = await self.request_device("GET", "/guide/airings")
        except Exception:
            airing_paths = []

        # We'll fetch more airings to build a grid (next 6 hours roughly)
        async def fetch_airing(path):
            async with sem:
                try:
                    return await self.request_device("GET", path)
                except Exception:
                    return None

        # Fetch first 1500 airing details to cover more channels/time
        airing_details = await asyncio.gather(*[fetch_airing(p) for p in airing_paths[:1500]])
        
        # Group airings by channel_path
        channel_to_airings = {}
        for a in airing_details:
            if not a or "airing_details" not in a:
                continue
            ad = a["airing_details"]
            c_path = ad.get("channel_path")
            if not c_path:
                continue
            
            if c_path not in channel_to_airings:
                channel_to_airings[c_path] = []
                
            channel_to_airings[c_path].append({
                "title": ad.get("show_title"),
                "description": a.get("episode", {}).get("description") or a.get("series", {}).get("description"),
                "start": ad.get("datetime"),
                "duration": ad.get("duration")
            })

        # 4. Assemble final grid
        grid = []
        for c in channels:
            c_path = next((path for path, ident in path_to_ident.items() if ident == c.identifier), None)
            
            # Sort airings by time
            airings = channel_to_airings.get(c_path, []) if c_path else []
            airings.sort(key=lambda x: x["start"])
            
            grid.append({
                "identifier": c.identifier,
                "call_sign": c.call_sign,
                "major": c.major,
                "minor": c.minor,
                "network": c.network,
                "display_name": c.display_name,
                "logo_url": logo_map.get(c.identifier),
                "airings": airings
            })
            
        return grid

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
