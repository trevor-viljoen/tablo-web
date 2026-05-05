import type { Channel } from "../api/tablo";

interface Props {
  channel: Channel;
  onClick: () => void;
}

const NETWORK_COLORS: Record<string, string> = {
  NBC:  "#d4a017",
  CBS:  "#2563eb",
  ABC:  "#dc2626",
  FOX:  "#f97316",
  PBS:  "#16a34a",
  CW:   "#7c3aed",
  ION:  "#0891b2",
  MeTV: "#9333ea",
};

export function ChannelCard({ channel, onClick }: Props) {
  const accent = NETWORK_COLORS[channel.network] ?? "#5b8af5";

  return (
    <button
      onClick={onClick}
      className="group relative flex flex-col rounded-2xl overflow-hidden
                 bg-surface-raised border border-surface-border
                 hover:border-accent/40 hover:channel-glow
                 transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]
                 text-left focus:outline-none focus:ring-2 focus:ring-accent/50"
    >
      {/* Color band */}
      <div className="h-1 w-full" style={{ background: accent }} />

      {/* Body */}
      <div className="flex items-center gap-4 p-4">
        {/* Channel number badge */}
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 font-bold text-sm"
          style={{ background: `${accent}18`, border: `1px solid ${accent}30`, color: accent }}
        >
          {channel.major}.{channel.minor}
        </div>

        <div className="min-w-0">
          <p className="font-bold text-base leading-tight truncate">{channel.call_sign}</p>
          {channel.network && (
            <p className="text-xs text-white/40 mt-0.5">{channel.network}</p>
          )}
        </div>

        {/* Play icon on hover */}
        <div className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="w-8 h-8 rounded-full flex items-center justify-center"
               style={{ background: accent }}>
            <svg className="w-3.5 h-3.5 text-white translate-x-px" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          </div>
        </div>
      </div>
    </button>
  );
}
