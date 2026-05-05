import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import auth, channels, stream
from .state import state, CONFIG_PATH


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Re-authenticate on startup if credentials are saved
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text())
            if cfg.get("email") and cfg.get("password"):
                await state.login(cfg["email"], cfg["password"])
        except Exception:
            pass  # Bad creds or network down — login screen will handle it
    yield
    await state.http.aclose()


app = FastAPI(title="Tablo Web", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(channels.router)
app.include_router(stream.router)


@app.get("/api/health")
async def health():
    return {"ok": True}
