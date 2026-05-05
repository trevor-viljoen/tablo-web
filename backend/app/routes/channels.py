from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..state import state

router = APIRouter(prefix="/api/channels", tags=["channels"])


class ChannelOut(BaseModel):
    identifier: str
    call_sign: str
    major: int
    minor: int
    network: str
    kind: str
    display_name: str


@router.get("", response_model=list[ChannelOut])
async def list_channels(refresh: bool = Query(False)):
    if not state.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        channels = await state.channels(refresh=refresh)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Tablo error: {e}")

    return [
        ChannelOut(
            identifier=c.identifier,
            call_sign=c.call_sign,
            major=c.major,
            minor=c.minor,
            network=c.network,
            kind=c.kind,
            display_name=c.display_name,
        )
        for c in channels
    ]
