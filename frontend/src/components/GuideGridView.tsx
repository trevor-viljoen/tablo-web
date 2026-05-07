import { useState, useEffect, useRef, useMemo } from "react";
import { api, type GridChannel, type Program } from "../api/tablo";

interface Props {
  onPlay: (channel: GridChannel) => void;
}

type ContentFilter = "all" | "movies" | "sports" | "news" | "reality" | "documentary" | "ota" | "fast";

const CONTENT_FILTERS: { id: ContentFilter; label: string; icon: string }[] = [
  { id: "all",          label: "All",          icon: "⊞" },
  { id: "movies",       label: "Movies",        icon: "🎬" },
  { id: "sports",       label: "Sports",        icon: "🏆" },
  { id: "news",         label: "News",          icon: "📰" },
  { id: "reality",      label: "Reality",       icon: "📺" },
  { id: "documentary",  label: "Documentary",   icon: "🎞" },
  { id: "ota",          label: "Broadcast",     icon: "📡" },
  { id: "fast",         label: "Streaming",     icon: "⚡" },
];

function airingMatchesFilter(air: Program, f: ContentFilter): boolean {
  if (f === "all") return true;
  const genres = air.genres ?? [];
  if (f === "movies")       return air.kind === "movieAiring";
  if (f === "sports")       return air.kind === "sportEvent" || genres.some(g => /sport/i.test(g));
  if (f === "news")         return genres.some(g => /news/i.test(g));
  if (f === "reality")      return genres.some(g => /reality/i.test(g));
  if (f === "documentary")  return genres.some(g => /documentary/i.test(g));
  return false; // ota/fast handled at channel level
}

function channelMatchesFilter(ch: GridChannel, f: ContentFilter): boolean {
  if (f === "all")  return true;
  if (f === "ota")  return ch.kind === "ota";
  if (f === "fast") return ch.kind === "ott";
  return ch.airings.some(a => airingMatchesFilter(a, f));
}

function useGridStream() {
  const [grid, setGrid] = useState<GridChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const map = new Map<string, GridChannel>();

    async function run() {
      setLoading(true);
      try {
        for await (const ch of api.guideGridStream(controller.signal)) {
          if (controller.signal.aborted) break;
          map.set(ch.identifier, ch);
          setGrid([...map.values()]);
          setLoading(false);
        }
      } catch (e) {
        if (!controller.signal.aborted) console.error("Grid stream error:", e);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    run();
    return () => controller.abort();
  }, []);

  return { grid, loading };
}

export function GuideGridView({ onPlay }: Props) {
  const { grid, loading: isLoading } = useGridStream();
  const [now, setNow] = useState(() => Date.now());
  const [contentFilter, setContentFilter] = useState<ContentFilter>("all");

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(timer);
  }, []);

  // Stable grid start: current hour, zeroed minutes/seconds
  const startTime = useMemo(() => {
    const d = new Date();
    d.setMinutes(0, 0, 0);
    return d.getTime();
  }, []);

  const HOUR_WIDTH = 400; // px per hour
  const TOTAL_HOURS = 6;

  const hours = Array.from({ length: TOTAL_HOURS }, (_, i) => {
    const d = new Date(startTime + i * 3600 * 1000);
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  });

  // Pixel offset of "now" from the left edge of the timeline
  const nowLeft = ((now - startTime) / 1000 / 3600) * HOUR_WIDTH;
  const nowVisible = nowLeft >= 0 && nowLeft <= HOUR_WIDTH * TOTAL_HOURS;

  const filteredGrid = contentFilter === "all" ? grid : grid.filter(ch => channelMatchesFilter(ch, contentFilter));

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-48 gap-4">
        <div className="w-12 h-12 rounded-full border-4 border-accent border-t-transparent animate-spin" />
        <p className="text-white/40 text-sm font-medium uppercase tracking-widest">Generating Grid...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
    {/* Content type filter chips */}
    <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
      {CONTENT_FILTERS.map(f => (
        <button
          key={f.id}
          onClick={() => setContentFilter(f.id)}
          className={`shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold tracking-wide transition
            ${contentFilter === f.id
              ? "bg-accent text-white shadow-lg shadow-accent/30"
              : "bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/80 border border-white/5"
            }`}
        >
          <span>{f.icon}</span>
          <span>{f.label}</span>
        </button>
      ))}
    </div>

    <div className="flex flex-col border border-white/5 rounded-3xl overflow-hidden bg-surface-raised shadow-2xl">
      {/* Time Header */}
      <div className="flex bg-black/40 border-b border-white/5 sticky top-0 z-20">
        <div className="w-32 shrink-0 border-r border-white/5 bg-black/20 flex items-center justify-center">
          <span className="text-[10px] font-black text-white/20 uppercase tracking-widest">Channel</span>
        </div>
        <div className="flex flex-1 overflow-x-auto no-scrollbar relative">
          {hours.map((h, i) => (
            <div key={i} className="shrink-0 font-mono text-[11px] font-bold text-white/30 flex items-center px-6 border-r border-white/5 h-10"
                 style={{ width: HOUR_WIDTH }}>
              {h}
            </div>
          ))}
          {/* Now marker in header */}
          {nowVisible && (
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-red-500 pointer-events-none z-30"
              style={{ left: nowLeft }}
            >
              <div className="w-2.5 h-2.5 rounded-full bg-red-500 -ml-1 mt-1" />
            </div>
          )}
        </div>
      </div>

      {/* Grid Rows */}
      <div className="flex flex-col max-h-[70vh] overflow-y-auto overflow-x-hidden">
        {filteredGrid.map((ch) => (
          <div key={ch.identifier} className="flex border-b border-white/5 hover:bg-white/[0.02] transition">
            {/* Channel Info */}
            <div className="w-32 shrink-0 p-4 border-r border-white/5 flex flex-col items-center justify-center gap-1.5 bg-black/10">
              <div className="w-12 h-10 flex items-center justify-center bg-black/30 rounded border border-white/5 p-1">
                {ch.logo_url ? (
                  <img src={ch.logo_url} alt={ch.call_sign} className="max-w-full max-h-full object-contain" />
                ) : (
                  <span className="text-[10px] font-bold text-white/40">{ch.call_sign}</span>
                )}
              </div>
              <span className="text-[11px] font-bold text-white/60 tabular-nums">
                {ch.major > 0 ? `${ch.major}.${ch.minor}` : "FAST"}
              </span>
            </div>

            {/* Programs Timeline */}
            <div className="flex flex-1 overflow-x-auto no-scrollbar py-2 relative h-24">
              {ch.airings.map((air, i) => {
                const airStart = new Date(air.start).getTime();
                const offsetSecs = (airStart - startTime) / 1000;
                let left = (offsetSecs / 3600) * HOUR_WIDTH;
                let width = (air.duration / 3600) * HOUR_WIDTH;

                if (left + width < 0) return null;

                // Clip programs that started before the grid start so the
                // title text stays visible at the left edge of the visible area.
                if (left < 0) {
                  width += left;
                  left = 0;
                }
                if (width < 20) return null;

                // Progress through this airing (0–100)
                const progress = air.duration > 0
                  ? Math.max(0, Math.min(100, ((now - airStart) / (air.duration * 1000)) * 100))
                  : 0;
                const isOnNow = progress > 0 && progress < 100;

                return (
                  <button
                    key={i}
                    onClick={() => onPlay(ch)}
                    className="absolute top-2 bottom-2 bg-white/5 hover:bg-white/10 border-l border-white/10 p-3 flex flex-col text-left group transition-colors rounded-sm overflow-hidden"
                    style={{ left, width: width - 4 }}
                  >
                    <p className="text-[11px] font-bold text-white/80 truncate group-hover:text-accent transition-colors">
                      {air.title}
                    </p>
                    <p className="text-[10px] text-white/20 line-clamp-1 mt-0.5">
                      {air.description || "Live TV Event"}
                    </p>
                    {/* Per-airing progress bar */}
                    {isOnNow && (
                      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-white/5">
                        <div className="h-full bg-accent/70" style={{ width: `${progress}%` }} />
                      </div>
                    )}
                  </button>
                );
              })}

              {/* Vertical "now" line across the row */}
              {nowVisible && (
                <div
                  className="absolute top-0 bottom-0 w-0.5 bg-red-500 pointer-events-none z-30"
                  style={{ left: nowLeft }}
                />
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
    </div>
  );
}
