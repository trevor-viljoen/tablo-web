import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Channel } from "../api/tablo";
import { ChannelCard } from "./ChannelCard";
import { VideoPlayer } from "./VideoPlayer";

interface Props {
  onLogout: () => void;
}

export function ChannelGrid({ onLogout }: Props) {
  const [playing, setPlaying] = useState<Channel | null>(null);
  const [filter, setFilter] = useState("");

  const { data: channels = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["channels"],
    queryFn: () => api.channels(),
    staleTime: 5 * 60_000,
  });

  const filtered = channels.filter(ch =>
    !filter || ch.call_sign.toLowerCase().includes(filter.toLowerCase()) ||
    ch.network.toLowerCase().includes(filter.toLowerCase()) ||
    ch.display_name.includes(filter)
  );

  return (
    <>
      {playing && (
        <VideoPlayer channel={playing} onClose={() => setPlaying(null)} />
      )}

      <div className="min-h-screen flex flex-col">
        {/* Header */}
        <header className="sticky top-0 z-10 glass border-b border-surface-border">
          <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-4">
            {/* Logo */}
            <div className="flex items-center gap-2.5 mr-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                   style={{ background: "linear-gradient(135deg, #5b8af5, #7c5bf5)" }}>
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M6 20.25h12m-7.5-3v3m3-3v3m-10.125-3h17.25c.621 0 1.125-.504 1.125-1.125V4.875C21 4.254 20.496 3.75 19.875 3.75H4.125C3.504 3.75 3 4.254 3 4.875v11.25c0 .621.504 1.125 1.125 1.125z" />
                </svg>
              </div>
              <span className="font-bold text-sm">Tablo</span>
            </div>

            {/* Search */}
            <div className="relative flex-1 max-w-xs">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/30"
                   fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                value={filter}
                onChange={e => setFilter(e.target.value)}
                placeholder="Filter channels…"
                className="w-full pl-9 pr-4 py-2 rounded-lg bg-surface-raised border border-surface-border
                           text-sm placeholder-white/25 focus:outline-none focus:ring-1 focus:ring-accent/50
                           transition"
              />
            </div>

            <div className="flex items-center gap-2 ml-auto">
              <span className="text-white/30 text-xs">{channels.length} channels</span>
              <button
                onClick={() => refetch()}
                className="w-8 h-8 rounded-lg glass flex items-center justify-center hover:bg-white/10 transition"
                title="Refresh"
              >
                <svg className="w-3.5 h-3.5 text-white/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
              <button
                onClick={onLogout}
                className="px-3 py-1.5 rounded-lg glass text-xs text-white/50 hover:text-white/80 hover:bg-white/10 transition"
              >
                Sign out
              </button>
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-8">
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-32 gap-4">
              <div className="w-8 h-8 rounded-full border-2 border-accent border-t-transparent animate-spin" />
              <p className="text-white/40 text-sm">Loading channels…</p>
            </div>
          )}

          {isError && (
            <div className="flex flex-col items-center justify-center py-32 gap-4">
              <p className="text-red-400 text-sm">Failed to load channels</p>
              <button onClick={() => refetch()} className="px-4 py-2 rounded-lg glass text-sm hover:bg-white/10 transition">
                Retry
              </button>
            </div>
          )}

          {!isLoading && !isError && (
            <>
              {filtered.length === 0 ? (
                <div className="flex items-center justify-center py-32">
                  <p className="text-white/30 text-sm">No channels match "{filter}"</p>
                </div>
              ) : (
                <div className="grid gap-3"
                     style={{ gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
                  {filtered.map(ch => (
                    <ChannelCard key={ch.identifier} channel={ch} onClick={() => setPlaying(ch)} />
                  ))}
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </>
  );
}
