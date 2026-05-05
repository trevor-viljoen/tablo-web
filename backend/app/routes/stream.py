"""HLS stream start + segment proxy."""

import re
from urllib.parse import urljoin, urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from ..state import state

router = APIRouter(tags=["stream"])


# ---------------------------------------------------------------------------
# Start stream
# ---------------------------------------------------------------------------

@router.post("/api/stream/{identifier}")
async def start_stream(identifier: str, request: Request):
    if not state.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        session_id, sess = await state.start_stream(identifier)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stream error: {e}")

    base = str(request.base_url).rstrip("/")
    proxy_url = f"{base}/api/hls/{session_id}/playlist.m3u8"
    return {"session_id": session_id, "proxy_url": proxy_url}


@router.delete("/api/stream/{session_id}")
async def stop_stream(session_id: str):
    state.stop_session(session_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# HLS proxy — manifest rewriting + segment passthrough
# ---------------------------------------------------------------------------

@router.get("/api/hls/{session_id}/{path:path}")
async def hls_proxy(session_id: str, path: str):
    sess = state.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Stream session not found")

    # The first request is always playlist.m3u8; map it to the real playlist URL.
    if path == "playlist.m3u8":
        target_url = sess.stream.playlist_url
    else:
        # Subsequent requests are segment paths relative to the Tablo device base.
        target_url = sess.base_url + "/" + path.lstrip("/")

    try:
        resp = await state.http.get(target_url, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Proxy error: {e}")

    content_type = resp.headers.get("content-type", "application/octet-stream")

    # Rewrite .m3u8 manifests so segment URLs point back through our proxy.
    if "mpegurl" in content_type or path.endswith(".m3u8"):
        rewritten = _rewrite_manifest(resp.text, session_id, sess.base_url)
        return Response(content=rewritten, media_type="application/vnd.apple.mpegurl",
                        headers={"Cache-Control": "no-cache",
                                 "Access-Control-Allow-Origin": "*"})

    # Binary segment passthrough — stream to avoid buffering the whole segment.
    return StreamingResponse(
        _iter_bytes(resp),
        media_type=content_type,
        headers={"Cache-Control": "max-age=30",
                 "Access-Control-Allow-Origin": "*"},
    )


async def _iter_bytes(resp):
    yield resp.content


def _rewrite_manifest(manifest: str, session_id: str, tablo_base: str) -> str:
    """Rewrite every segment/sub-playlist URI in an HLS manifest to go through our proxy."""
    lines = []
    for line in manifest.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped == "":
            lines.append(line)
            continue

        # Convert absolute Tablo URLs → our proxy path
        if stripped.startswith("http://") or stripped.startswith("https://"):
            parsed = urlparse(stripped)
            rel = parsed.path.lstrip("/")
        else:
            # Relative path — resolve against tablo base
            parsed = urlparse(urljoin(tablo_base + "/", stripped))
            rel = parsed.path.lstrip("/")

        lines.append(f"/api/hls/{session_id}/{rel}")

    return "\n".join(lines)
