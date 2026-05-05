import { useEffect, useRef, useCallback } from "react";
import Hls from "hls.js";

export function usePlayer(videoRef: React.RefObject<HTMLVideoElement | null>) {
  const hlsRef = useRef<Hls | null>(null);

  const load = useCallback((url: string) => {
    const video = videoRef.current;
    if (!video) return;

    // Tear down any previous instance
    hlsRef.current?.destroy();
    hlsRef.current = null;

    if (Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true, lowLatencyMode: false });
      hls.loadSource(url);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => { video.play().catch(() => {}); });
      hlsRef.current = hls;
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Safari native HLS
      video.src = url;
      video.addEventListener("loadedmetadata", () => { video.play().catch(() => {}); }, { once: true });
    }
  }, [videoRef]);

  const destroy = useCallback(() => {
    hlsRef.current?.destroy();
    hlsRef.current = null;
    if (videoRef.current) {
      videoRef.current.src = "";
    }
  }, [videoRef]);

  useEffect(() => () => { hlsRef.current?.destroy(); }, []);

  return { load, destroy };
}
