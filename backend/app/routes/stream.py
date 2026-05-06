"""Minimal working version."""

import asyncio
import subprocess
from pathlib import Path
from urllib.parse import urljoin, urlparse

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from ..state import state

router = APIRouter(tags=["stream"])

TRANSCODE_DIR = Path("/tmp/tablo_transcode")
TRANSCODE_DIR.mkdir(exist_ok=True)

transcode_procs: dict[str, subprocess.Popen] = {}


# ─────────────────────────────────────────────────────────────────────────────
# TRANSCODED
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/transcoded/{session_id}/{path:path}")
async def transcoded_stream(session_id: str, path: str, request: Request):
    # Security: Ensure session_id is a valid hex string to prevent path traversal
    if not all(c in "0123456789abcdefABCDEF" for c in session_id):
        raise HTTPException(400, "Invalid session ID")

    session_dir = TRANSCODE_DIR / session_id
    # Security: Normalize path and prevent traversing out of session_dir
    try:
        file_path = (session_dir / path).resolve()
        if not str(file_path).startswith(str(session_dir.resolve())):
            raise ValueError("Traversal attempt")
    except Exception:
        raise HTTPException(400, "Invalid path")

    # Wait up to 10 seconds (async) for the manifest to appear if it's the playlist
    if path == "playlist.m3u8" and not file_path.exists():
        for _ in range(20):
            if file_path.exists():
                break
            await asyncio.sleep(0.5)

    if not file_path.exists() or not file_path.is_file():
        # Check if FFmpeg is still alive to provide a better error
        proc = transcode_procs.get(session_id)
        status = "unknown"
        if proc:
            status = "alive" if proc.poll() is None else f"exited with {proc.returncode}"
        raise HTTPException(404, f"File not found: {path} (Transcoder: {status})")

    # Official HLS media type
    hls_type = "application/vnd.apple.mpegurl"

    if path.endswith(".m3u8"):
        return FileResponse(
            file_path,
            media_type=hls_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
                "Content-Disposition": "inline"
            }
        )
    elif path.endswith(".ts"):
        return FileResponse(
            file_path,
            media_type="video/mp2t",
            headers={"Access-Control-Allow-Origin": "*"}
        )

    return FileResponse(file_path, headers={"Access-Control-Allow-Origin": "*"})


# ---------------------------------------------------------------------------
# Start stream (with smart transcoding)
# ---------------------------------------------------------------------------

@router.post("/stream/{identifier}")
async def start_stream(
    identifier: str,
    request: Request,
    transcode: bool | None = Query(default=None)
):
    if not state.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        session_id, sess = await state.start_stream(identifier)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stream error: {e}")

    # NOTE: We use root-relative paths for the frontend so it works through the proxy
    if transcode is None:
        ua = request.headers.get("user-agent", "").lower()
        is_browser = any(x in ua for x in ["mozilla", "chrome", "safari", "firefox", "edge"])
        transcode = is_browser

    if transcode:
        await start_transcoder(session_id, sess.stream.playlist_url)
        stream_url = f"/api/transcoded/{session_id}/playlist.m3u8"
    else:
        stream_url = f"/api/hls/{session_id}/playlist.m3u8"

    return {
        "session_id": session_id,
        "proxy_url": f"/api/hls/{session_id}/playlist.m3u8",
        "stream_url": stream_url,
        "transcoded": transcode
    }


# ---------------------------------------------------------------------------
# Stop stream + cleanup
# ---------------------------------------------------------------------------

@router.delete("/stream/{session_id}")
async def stop_stream(session_id: str):
    if proc := transcode_procs.pop(session_id, None):
        proc.kill()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.terminate()

    session_dir = TRANSCODE_DIR / session_id
    if session_dir.exists():
        for f in session_dir.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass
        try:
            session_dir.rmdir()
        except Exception:
            pass

    state.stop_session(session_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Raw HLS proxy
# ---------------------------------------------------------------------------

@router.get("/hls/{session_id}/{path:path}")
async def hls_proxy(session_id: str, path: str, request: Request):
    sess = state.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Stream session not found")

    if path == "playlist.m3u8":
        target_url = sess.stream.playlist_url
    else:
        # Preserve tokens if passed as query params
        query = str(request.url.query)
        target_url = sess.base_url + "/" + path.lstrip("/")
        if query:
            target_url += "?" + query

    try:
        resp = await state.http.get(target_url, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Proxy error: {e}")

    content_type = resp.headers.get("content-type", "application/octet-stream")
    hls_type = "application/vnd.apple.mpegurl"

    if "mpegurl" in content_type.lower() or path.endswith(".m3u8"):
        rewritten = _rewrite_manifest(resp.text, session_id, target_url)
        return Response(
            content=rewritten, 
            media_type=hls_type,
            headers={
                "Cache-Control": "no-cache", 
                "Access-Control-Allow-Origin": "*",
                "Content-Disposition": "inline"
            }
        )

    return StreamingResponse(
        _iter_bytes(resp),
        media_type=content_type,
        headers={"Cache-Control": "max-age=30", "Access-Control-Allow-Origin": "*"},
    )


async def _iter_bytes(resp):
    yield resp.content


def _rewrite_manifest(manifest: str, session_id: str, playlist_url: str) -> str:
    # Use the playlist URL's directory as the base for relative paths
    playlist_base = playlist_url.rsplit("/", 1)[0] + "/"
    
    lines = []
    for line in manifest.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped == "":
            lines.append(line)
            continue

        # Preserve the entire path AND query string (for tokens)
        if stripped.startswith(("http://", "https://")):
            parsed = urlparse(stripped)
            # path including query
            rel = parsed.path.lstrip("/")
            if parsed.query:
                rel += "?" + parsed.query
        else:
            # It's a relative path on the Tablo, resolve against playlist_base
            full_url = urljoin(playlist_base, stripped)
            parsed = urlparse(full_url)
            rel = parsed.path.lstrip("/")
            if parsed.query:
                rel += "?" + parsed.query

        lines.append(f"/api/hls/{session_id}/{rel}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Status check
# ---------------------------------------------------------------------------

@router.get("/transcode/status/{session_id}")
async def transcode_status(session_id: str):
    proc = transcode_procs.get(session_id)
    session_dir = TRANSCODE_DIR / session_id
    
    log_content = ""
    log_file = session_dir / "ffmpeg.log"
    if log_file.exists():
        try:
            # Get last 20 lines of log
            lines = log_file.read_text().splitlines()
            log_content = "\n".join(lines[-20:])
        except Exception:
            pass

    if not proc:
        return {"status": "inactive", "log": log_content}

    return {
        "status": "active" if proc.poll() is None else "stopped",
        "return_code": proc.returncode,
        "files": [f.name for f in session_dir.glob("*") if f.is_file()],
        "log": log_content
    }


# ---------------------------------------------------------------------------
# Start FFmpeg
# ---------------------------------------------------------------------------

async def start_transcoder(session_id: str, input_url: str):
    session_dir = TRANSCODE_DIR / session_id
    session_dir.mkdir(exist_ok=True, parents=True)

    log_file = session_dir / "ffmpeg.log"

    # Use a slightly more robust ffmpeg command
    cmd = [
        "ffmpeg",
        "-y", # Overwrite
        "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
        "-i", input_url,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-maxrate", "2000k", "-bufsize", "4000k",
        "-pix_fmt", "yuv420p", "-g", "60",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-f", "hls",
        "-hls_time", "6",
        "-hls_list_size", "10",
        "-hls_segment_filename", "%03d.ts",
        "-hls_flags", "delete_segments+independent_segments",
        "-loglevel", "info",
        "playlist.m3u8"
    ]

    with open(log_file, "w") as f:
        f.write(f"Starting FFmpeg for session {session_id}\n")
        f.write(f"Input: {input_url}\n")
        f.write(f"Command: {' '.join(cmd)}\n\n")
        f.flush()
        
        proc = subprocess.Popen(
            cmd,
            stdout=f,
            stderr=subprocess.STDOUT,
            cwd=session_dir
        )

    transcode_procs[session_id] = proc
