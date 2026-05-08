"""IPTV-compatible M3U playlist and XMLTV EPG for Plex / Jellyfin."""

import asyncio
import subprocess
import time
from datetime import datetime, timedelta
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from ..state import state

router = APIRouter(prefix="/api/iptv", tags=["iptv"])

# EPG cache — generated once, refreshed in background every 15 minutes
_epg_cache: bytes = b""
_epg_cache_time: float = 0.0
_epg_lock = asyncio.Lock()
_EPG_TTL = 14400  # seconds — 4 hours (EPG build fetches ~15k airings, worth keeping longer)


async def _build_epg() -> bytes:
    grid = await state.get_epg_guide()

    tv = Element("tv", attrib={
        "source-info-name": "Tablo",
        "generator-info-name": "tablo-web",
    })

    def _ch_id(ch: dict) -> str:
        major, minor = ch.get("major", 0), ch.get("minor", 0)
        return f"{major}.{minor}" if major > 0 else ch.get("call_sign", ch["identifier"])

    for ch in grid:
        ch_id = _ch_id(ch)
        ch_el = SubElement(tv, "channel", id=ch_id)
        SubElement(ch_el, "display-name").text = ch["display_name"]
        SubElement(ch_el, "display-name").text = ch_id
        SubElement(ch_el, "display-name").text = ch.get("network") or ch["display_name"]
        if ch.get("logo_url"):
            SubElement(ch_el, "icon", src=ch["logo_url"])

    for ch in grid:
        ch_id = _ch_id(ch)
        for air in ch.get("airings", []):
            start_str = air.get("start")
            if not start_str:
                continue
            try:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                stop_dt = start_dt + timedelta(seconds=air.get("duration") or 3600)
                fmt = "%Y%m%d%H%M%S %z"
                prog = SubElement(
                    tv, "programme",
                    start=start_dt.strftime(fmt),
                    stop=stop_dt.strftime(fmt),
                    channel=ch_id,
                )
                SubElement(prog, "title").text = air.get("title") or "Unknown"
                if air.get("description"):
                    SubElement(prog, "desc").text = air["description"]
                for genre in (air.get("genres") or []):
                    SubElement(prog, "category").text = genre
            except Exception:
                continue

    return (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<!DOCTYPE tv SYSTEM "xmltv.dtd">\n'
        + tostring(tv, encoding="unicode").encode("utf-8")
    )


async def _get_epg_cached() -> bytes:
    global _epg_cache, _epg_cache_time
    now = time.monotonic()

    if _epg_cache and now - _epg_cache_time < _EPG_TTL:
        return _epg_cache

    async with _epg_lock:
        # Re-check after acquiring lock
        if _epg_cache and time.monotonic() - _epg_cache_time < _EPG_TTL:
            return _epg_cache
        _epg_cache = await _build_epg()
        _epg_cache_time = time.monotonic()
        return _epg_cache


@router.get("/playlist.m3u")
async def m3u_playlist(request: Request):
    """M3U8 channel list for Plex / Jellyfin Live TV tuner configuration.

    Stream URLs use /api/iptv/live/{identifier} which starts a session and
    redirects to the HLS proxy — no session management needed on the client.
    """
    if not state.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")

    channels = await state.channels()
    base = str(request.base_url).rstrip("/")

    lines = [f'#EXTM3U x-tvg-url="{base}/api/iptv/epg.xml"']
    for ch in channels:
        name = ch.display_name
        major, minor = ch.major, ch.minor
        ch_num = f"{major}.{minor}" if major > 0 else ""
        group = "Broadcast" if ch.kind == "ota" else "Streaming"
        tvg_id = ch.identifier

        extinf = (
            f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}"'
            f' group-title="{group}"'
        )
        if ch_num:
            extinf += f' tvg-chno="{ch_num}"'
        extinf += f",{name}"
        if ch_num:
            extinf += f" ({ch_num})"

        lines.append(extinf)
        lines.append(f"{base}/api/iptv/live/{tvg_id}")

    return Response(
        "\n".join(lines),
        media_type="application/x-mpegURL",
        headers={"Content-Disposition": 'attachment; filename="tablo.m3u"'},
    )


@router.get("/epg.xml")
async def epg_xml():
    """XMLTV EPG for Plex / Jellyfin — cached, refreshes every 15 minutes."""
    if not state.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")
    xml_body = await _get_epg_cached()
    return Response(content=xml_body, media_type="application/xml")


async def _tuner_count() -> int:
    try:
        info = await state.request_device("GET", "/server/info")
        return int(info.get("model", {}).get("tuners", 4))
    except Exception:
        return 4


@router.get("")
@router.get("/")
async def iptv_root(request: Request):
    """HDHomeRun root probe — some clients hit the base URL before discover.json."""
    return await hdhr_discover(request)


@router.get("/discover.json")
async def hdhr_discover(request: Request):
    """HDHomeRun device discovery — Plex probes this to identify the tuner."""
    if not state.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Start EPG pre-warm early so it's ready by the time Plex asks for it
    if not _epg_cache:
        asyncio.create_task(_get_epg_cached())
    base = str(request.base_url).rstrip("/")
    return {
        "FriendlyName": "Tablo",
        "Manufacturer": "Tablo Network",
        "ModelNumber": "HDTC-2US",
        "FirmwareName": "hdhomerun3_atsc",
        "FirmwareVersion": "20190621",
        "DeviceID": "12345678",
        "DeviceAuth": "tablo",
        "TunerCount": await _tuner_count(),
        "BaseURL": f"{base}/api/iptv",
        "LineupURL": f"{base}/api/iptv/lineup.json",
    }


@router.get("/lineup_status.json")
async def hdhr_lineup_status():
    """HDHomeRun lineup status — tells Plex the lineup is ready, no scan needed."""
    if not state.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "ScanInProgress": 0,
        "ScanPossible": 0,
        "Source": "Antenna",
        "SourceList": ["Antenna"],
    }


@router.post("/lineup.json")
async def hdhr_lineup_scan():
    """HDHomeRun scan trigger — acknowledge immediately so Plex doesn't wait."""
    return {}


@router.post("/playlist.m3u/lineup.json")
async def hdhr_lineup_scan_alias():
    return {}


@router.get("/lineup.json")
async def hdhr_lineup(request: Request):
    """HDHomeRun channel lineup — Plex uses this to build its channel list."""
    if not state.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Pre-warm the EPG cache in the background so it's ready when Plex asks next
    asyncio.create_task(_get_epg_cached())
    channels = await state.channels()
    base = str(request.base_url).rstrip("/")
    return [
        {
            "GuideNumber": f"{ch.major}.{ch.minor}" if ch.major > 0 else ch.call_sign,
            "GuideName": ch.display_name or ch.network,
            "URL": f"{base}/api/iptv/live/{ch.identifier}",
        }
        for ch in channels
    ]


@router.get("/playlist.m3u/discover.json")
async def hdhr_discover_alias(request: Request):
    if not state.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")
    base = str(request.base_url).rstrip("/")
    return {
        "FriendlyName": "Tablo",
        "Manufacturer": "Tablo Network",
        "ModelNumber": "HDTC-2US",
        "FirmwareName": "hdhomerun3_atsc",
        "FirmwareVersion": "20190621",
        "DeviceID": "12345678",
        "DeviceAuth": "tablo",
        "TunerCount": await _tuner_count(),
        "BaseURL": f"{base}/api/iptv/playlist.m3u",
        "LineupURL": f"{base}/api/iptv/playlist.m3u/lineup.json",
    }

@router.get("/playlist.m3u/lineup_status.json")
async def hdhr_lineup_status_alias():
    return await hdhr_lineup_status()

@router.get("/playlist.m3u/lineup.json")
async def hdhr_lineup_alias(request: Request):
    return await hdhr_lineup(request)


@router.get("/live/{identifier}")
async def live_stream(identifier: str, request: Request):
    """Stream a channel as raw MPEG-TS.

    Plex treats HDHomeRun URLs as MPEG-TS streams and passes MPEG-TS-specific
    FFmpeg options (-scan_all_pmts) when opening them. Returning HLS causes a
    format mismatch. We remux the Tablo's HLS into a continuous MPEG-TS pipe so
    Plex (and Jellyfin) can transcode it for their clients.
    """
    if not state.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        session_id, sess = await state.start_stream(identifier)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stream error: {e}")

    playlist_url = sess.stream.playlist_url

    proc = subprocess.Popen(
        [
            "ffmpeg", "-y",
            "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
            "-i", playlist_url,
            "-c", "copy",
            "-f", "mpegts",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    async def generate():
        loop = asyncio.get_event_loop()
        try:
            while True:
                chunk = await loop.run_in_executor(None, proc.stdout.read, 65536)
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                proc.kill()
                proc.wait()
            except Exception:
                pass
            state.stop_session(session_id)

    return StreamingResponse(
        generate(),
        media_type="video/mp2t",
        headers={"Cache-Control": "no-cache"},
    )
