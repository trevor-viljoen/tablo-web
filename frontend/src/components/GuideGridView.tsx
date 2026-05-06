import { useQuery } from "@tanstack/react-query";
import { api, type GridChannel } from "../api/tablo";

interface Props {
  onPlay: (channel: GridChannel) => void;
}

export function GuideGridView({ onPlay }: Props) {
  const { data: grid = [], isLoading } = useQuery({
    queryKey: ["guide-grid"],
    queryFn: () => api.guideGrid(),
    staleTime: 5 * 60_000,
  });

  // Generate hours for the header
  const startTime = new Date();
  startTime.setMinutes(0, 0, 0);
  const hours = Array.from({ length: 6 }, (_, i) => {
    const d = new Date(startTime.getTime() + i * 3600 * 1000);
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  });

  const HOUR_WIDTH = 400; // px per hour

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-48 gap-4">
        <div className="w-12 h-12 rounded-full border-4 border-accent border-t-transparent animate-spin" />
        <p className="text-white/40 text-sm font-medium uppercase tracking-widest">Generating Grid...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col border border-white/5 rounded-3xl overflow-hidden bg-surface-raised shadow-2xl">
      {/* Time Header */}
      <div className="flex bg-black/40 border-b border-white/5 sticky top-0 z-20">
        <div className="w-32 shrink-0 border-r border-white/5 bg-black/20 flex items-center justify-center">
           <span className="text-[10px] font-black text-white/20 uppercase tracking-widest">Channel</span>
        </div>
        <div className="flex flex-1 overflow-x-auto no-scrollbar">
          {hours.map((h, i) => (
            <div key={i} className="shrink-0 font-mono text-[11px] font-bold text-white/30 flex items-center px-6 border-r border-white/5 h-10" 
                 style={{ width: HOUR_WIDTH }}>
              {h}
            </div>
          ))}
        </div>
      </div>

      {/* Grid Rows */}
      <div className="flex flex-col max-h-[70vh] overflow-y-auto overflow-x-hidden">
        {grid.map((ch) => (
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
                 const gridStart = startTime.getTime();
                 const offsetSecs = (airStart - gridStart) / 1000;
                 const left = (offsetSecs / 3600) * HOUR_WIDTH;
                 const width = (air.duration / 3600) * HOUR_WIDTH;

                 if (left + width < 0) return null;

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
                   </button>
                 );
               })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
