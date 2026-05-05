from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..state import state

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class DeviceOut(BaseModel):
    sid: str
    name: str
    local_url: str


class LoginResponse(BaseModel):
    devices: list[DeviceOut]
    active_sid: str | None


@router.get("/status")
async def status():
    return {
        "authenticated": state.is_authenticated,
        "devices": [{"sid": d.sid, "name": d.name} for d in state.devices],
        "active_sid": state.active_device.sid if state.active_device else None,
    }


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    try:
        devices = await state.login(req.email, req.password)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
    return LoginResponse(
        devices=[DeviceOut(sid=d.sid, name=d.name, local_url=d.local_url) for d in devices],
        active_sid=state.active_device.sid if state.active_device else None,
    )


@router.post("/device/{sid}")
async def select_device(sid: str):
    try:
        dev = await state.select_device(sid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"sid": dev.sid, "name": dev.name}


@router.delete("/logout")
async def logout():
    state.clear_config()
    return {"ok": True}
