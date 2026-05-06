import { useEffect, useRef, useState, useCallback } from "react";
import { usePlayer } from "../hooks/usePlayer";
import { api } from "../api/tablo";
import type { Channel } from "../api/tablo";

interface Props {
  channel: Channel;
  onClose: () => void;
}

export function VideoPlayer({ channel, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const { load, destroy, error: playerError } = usePlayer(videoRef);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [showControls, setShowControls] = useState(true);
  const hideTimer = useRef<ReturnType<typeof setTimeout>>(null);

  const combinedError = apiError || playerError;

  // Start stream on mount
  useEffect(() => {
    let cancelled = false;

    api.startStream(channel.identifier)
      .then(({ session_id, stream_url }) => {
        if (cancelled) return;
        setSessionId(session_id);
        load(stream_url);
        setLoading(false);
      })
      .catch((e) => {
        if (!cancelled) { 
          setApiError(e instanceof Error ? e.message : String(e)); 
          setLoading(false); 
        }
      });

    return () => {
      cancelled = true;
      destroy();
    };
  }, [channel.identifier, load, destroy]);

  // Stop stream on unmount
  useEffect(() => {
    return () => {
      if (sessionId) api.stopStream(sessionId).catch(() => {});
    };
  }, [sessionId]);

  // Auto-hide controls
  const resetHideTimer = useCallback(() => {
    setShowControls(true);
    if (hideTimer.current) clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => setShowControls(false), 3500);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setShowControls(false), 3500);
    return () => clearTimeout(timer);
  }, []);

  // Keyboard
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" || e.key === "q") onClose();
      if (e.key === "f") videoRef.current?.requestFullscreen?.();
      resetHideTimer();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, resetHideTimer]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black flex items-center justify-center"
      onMouseMove={resetHideTimer}
      onClick={resetHideTimer}
    >
      {/* Video */}
      <video
        ref={videoRef}
        className="w-full h-full object-contain"
        playsInline
        autoPlay
        muted // Critical for autoplay in most browsers
      />

      {/* Loading / error overlay */}
      {(loading || combinedError) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black/70">
          {loading && (
            <>
              <div className="w-10 h-10 rounded-full border-2 border-accent border-t-transparent animate-spin" />
              <p className="text-white/60 text-sm">Starting stream…</p>
            </>
          )}
          {combinedError && (
            <>
              <p className="text-red-400 text-sm max-w-xs text-center">{combinedError}</p>
              <button onClick={onClose} className="px-4 py-2 rounded-lg glass text-sm hover:bg-white/10 transition">
                Close
              </button>
            </>
          )}
        </div>
      )}

      {/* Controls overlay */}
      <div
        className={`absolute inset-0 flex flex-col justify-between p-6 transition-opacity duration-300 pointer-events-none
          ${showControls ? "opacity-100" : "opacity-0"}`}
        style={{ background: "linear-gradient(to bottom, rgba(0,0,0,0.7) 0%, transparent 30%, transparent 70%, rgba(0,0,0,0.8) 100%)" }}
      >
        {/* Top bar */}
        <div className="flex items-center justify-between pointer-events-auto">
          <div>
            <p className="text-xs font-semibold tracking-widest text-white/50 uppercase mb-0.5">{channel.network || channel.kind.toUpperCase()}</p>
            <p className="text-2xl font-bold">{channel.display_name}</p>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 rounded-full glass flex items-center justify-center hover:bg-white/10 transition"
            title="Close (Esc)"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Bottom bar */}
        <div className="flex items-center justify-between pointer-events-auto">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-sm font-medium text-white/80">LIVE</span>
          </div>
          <button
            onClick={() => videoRef.current?.requestFullscreen?.()}
            className="w-9 h-9 rounded-lg glass flex items-center justify-center hover:bg-white/10 transition"
            title="Fullscreen (F)"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-5h-4m4 0v4m0-4l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
