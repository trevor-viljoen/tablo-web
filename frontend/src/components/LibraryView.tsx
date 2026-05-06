import { useQuery } from "@tanstack/react-query";
import { api } from "../api/tablo";

export function LibraryView() {
  const { data: recordings = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["library"],
    queryFn: () => api.library(),
    staleTime: 5 * 60_000,
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-48 gap-4">
        <div className="w-12 h-12 rounded-full border-4 border-accent border-t-transparent animate-spin" />
        <p className="text-white/40 text-sm font-medium uppercase tracking-widest">Accessing Library...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-48 gap-6 text-center">
        <p className="text-red-400 font-bold">Failed to load recordings</p>
        <button onClick={() => refetch()} className="px-6 py-2 rounded-xl glass text-sm hover:bg-white/5 transition">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="grid gap-6" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
      {recordings.length === 0 ? (
        <div className="col-span-full py-48 text-center bg-white/5 rounded-3xl border border-white/5">
          <p className="text-white/20 font-black tracking-widest uppercase">No Recordings Found</p>
        </div>
      ) : (
        recordings.map((rec) => (
          <div key={rec.identifier} className="group flex flex-col bg-surface-raised border border-surface-border rounded-2xl overflow-hidden hover:border-accent/40 transition shadow-lg">
            <div className="aspect-video bg-black/40 relative">
               {rec.thumbnail ? (
                 <img src={rec.thumbnail} alt={rec.title || ""} className="w-full h-full object-cover" />
               ) : (
                 <div className="w-full h-full flex items-center justify-center text-white/10 uppercase font-black text-xl italic">
                   Tablo
                 </div>
               )}
               <div className="absolute bottom-3 right-3 px-2 py-1 rounded bg-black/80 text-[10px] font-bold text-white tabular-nums">
                 {Math.round(rec.duration / 60)} MIN
               </div>
            </div>
            <div className="p-5 flex flex-col gap-1">
              <h3 className="font-bold text-white truncate leading-tight">{rec.title || "Untitled Recording"}</h3>
              <p className="text-xs text-white/40 line-clamp-2 leading-relaxed min-h-[2.5rem]">
                {rec.description || "No description available"}
              </p>
              <div className="mt-4 flex items-center justify-between">
                <span className="text-[10px] font-black text-white/20 uppercase tracking-widest">
                   {new Date(rec.start).toLocaleDateString()}
                </span>
                <button className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center hover:bg-accent hover:text-white transition text-white/40">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
