import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type GuideChannel, type GridChannel } from "../api/tablo";
import { ChannelCard } from "./ChannelCard";
import { VideoPlayer } from "./VideoPlayer";
import { LibraryView } from "./LibraryView";
import { GuideGridView } from "./GuideGridView";

interface Props {
  onLogout: () => void;
}

type Tab = "live" | "grid" | "library";

export function ChannelGrid({ onLogout }: Props) {
  const [playing, setPlaying] = useState<GuideChannel | null>(null);
  const [filter, setFilter] = useState("");
  const [activeTab, setTab] = useState<Tab>("live");
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(timer);
  }, []);

  const { data: channels = [], isLoading } = useQuery({
    queryKey: ["guide"],
    queryFn: () => api.guide(),
    staleTime: 60_000,
    refetchInterval: 60_000,
    enabled: activeTab === "live"
  });

  const filtered = channels.filter(ch =>
    !filter || 
    ch.call_sign.toLowerCase().includes(filter.toLowerCase()) ||
    ch.network.toLowerCase().includes(filter.toLowerCase()) ||
    ch.current_program?.title?.toLowerCase().includes(filter.toLowerCase()) ||
    ch.display_name.includes(filter)
  );

  const handlePlay = (ch: GuideChannel | GridChannel) => {
    const isGrid = 'airings' in ch;
    const guideCh: GuideChannel = {
      identifier: ch.identifier,
      call_sign: ch.call_sign,
      major: ch.major,
      minor: ch.minor,
      network: ch.network,
      kind: ch.kind,
      display_name: ch.display_name,
      logo_url: ch.logo_url,
      current_program: isGrid ? (ch as GridChannel).airings[0] : (ch as GuideChannel).current_program
    };
    setPlaying(guideCh);
  };

  return (
    <>
      {playing && (
        <VideoPlayer 
          key={playing.identifier}
          channel={{
            identifier: playing.identifier,
            call_sign: playing.call_sign,
            major: playing.major,
            minor: playing.minor,
            network: playing.network,
            kind: playing.kind,
            display_name: playing.display_name
          }} 
          onClose={() => setPlaying(null)} 
        />
      )}

      <div className="min-h-screen flex flex-col bg-surface">
        {/* Header */}
        <header className="sticky top-0 z-10 glass border-b border-surface-border">
          <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-4">
            {/* Logo */}
            <div className="flex items-center gap-2.5 mr-6">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 shadow-lg shadow-accent/20"
                   style={{ background: "linear-gradient(135deg, #5b8af5, #7c5bf5)" }}>
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 20.25h12m-7.5-3v3m3-3v3m-10.125-3h17.25c.621 0 1.125-.504 1.125-1.125V4.875C21 4.254 20.496 3.75 19.875 3.75H4.125C3.504 3.75 3 4.254 3 4.875v11.25c0 .621.504 1.125 1.125 1.125z" />
                </svg>
              </div>
              <span className="font-black text-lg tracking-tight uppercase italic italic-accent">Tablo</span>
            </div>

            {/* Navigation Tabs */}
            <nav className="flex items-center gap-1 mr-auto">
              <button 
                onClick={() => setTab("live")}
                className={`px-4 py-1.5 rounded-full text-sm font-bold tracking-wide transition
                           ${activeTab === "live" ? "bg-accent/15 text-accent" : "text-white/40 hover:text-white/60"}`}
              >
                Live TV
              </button>
              <button 
                onClick={() => setTab("grid")}
                className={`px-4 py-1.5 rounded-full text-sm font-bold tracking-wide transition
                           ${activeTab === "grid" ? "bg-accent/15 text-accent" : "text-white/40 hover:text-white/60"}`}
              >
                Guide
              </button>
              <button 
                onClick={() => setTab("library")}
                className={`px-4 py-1.5 rounded-full text-sm font-bold tracking-wide transition
                           ${activeTab === "library" ? "bg-accent/15 text-accent" : "text-white/40 hover:text-white/60"}`}
              >
                Library
              </button>
            </nav>

            {/* Search */}
            {activeTab === "live" && (
              <div className="relative flex-1 max-w-sm">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20"
                     fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  value={filter}
                  onChange={e => setFilter(e.target.value)}
                  placeholder="Search programs, channels..."
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/5 border border-white/5
                             text-sm placeholder-white/20 focus:outline-none focus:ring-1 focus:ring-accent/40
                             focus:bg-white/10 transition shadow-inner"
                />
              </div>
            )}

            <div className="flex items-center gap-4 ml-4">
              <button
                onClick={onLogout}
                className="px-4 py-2 rounded-xl glass text-xs font-bold text-white/40 hover:text-red-400 hover:bg-red-500/10 transition border border-transparent hover:border-red-500/20"
              >
                LOGOUT
              </button>
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-10">
          {activeTab === "live" && (
            <>
              <div className="mb-8 flex items-baseline justify-between">
                <div>
                  <h1 className="text-3xl font-black tracking-tight text-white mb-2 uppercase italic">ON AIR NOW</h1>
                  <p className="text-white/30 text-sm font-medium tracking-wide uppercase">Browser your local guide and start watching instantly</p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-mono text-accent font-bold">
                    {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                  <p className="text-[10px] text-white/20 font-black tracking-widest uppercase">Live Guide</p>
                </div>
              </div>

              {isLoading && !channels.length ? (
                <div className="flex flex-col items-center justify-center py-48 gap-6 bg-white/5 rounded-3xl border border-white/5 shadow-2xl">
                  <div className="w-12 h-12 rounded-full border-4 border-accent border-t-transparent animate-spin" />
                  <p className="text-white font-black tracking-tighter text-xl uppercase mb-1">Building Your Guide</p>
                </div>
              ) : (
                <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }}>
                  {filtered.map(ch => (
                    <ChannelCard key={ch.identifier} channel={ch} now={now} onClick={() => setPlaying(ch)} />
                  ))}
                </div>
              )}
            </>
          )}

          {activeTab === "grid" && (
            <div className="flex flex-col gap-6">
               <div className="mb-4">
                 <h1 className="text-3xl font-black tracking-tight text-white mb-2 uppercase italic">TV GUIDE</h1>
                 <p className="text-white/30 text-sm font-medium tracking-wide uppercase">Traditional timeline view of all upcoming airings</p>
               </div>
               <GuideGridView onPlay={handlePlay} />
            </div>
          )}

          {activeTab === "library" && (
            <div className="flex flex-col gap-6">
              <div className="mb-4">
                 <h1 className="text-3xl font-black tracking-tight text-white mb-2 uppercase italic">RECORDINGS</h1>
                 <p className="text-white/30 text-sm font-medium tracking-wide uppercase">Watch and manage your saved content</p>
              </div>
              <LibraryView />
            </div>
          )}
        </main>
      </div>
    </>
  );
}
