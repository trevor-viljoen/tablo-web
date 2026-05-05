"""Global in-process state — auth, active device, live stream sessions."""

import json
import uuid
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
        self._http = httpx.AsyncClient(timeout=15)

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

    async def channels(self, refresh: bool = False) -> list[TabloChannel]:
        if self.active_device is None:
            raise RuntimeError("No active device")
        if self._channels is None or refresh:
            client = TabloClient(self.active_device)
            self._channels = await _run_sync(client.channels)
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
