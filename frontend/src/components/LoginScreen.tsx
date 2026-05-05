import { useState } from "react";
import { api } from "../api/tablo";

interface Props {
  onSuccess: () => void;
}

export function LoginScreen({ onSuccess }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.login(email, password);
      onSuccess();
    } catch (err: any) {
      setError(err.message ?? "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6"
         style={{ background: "radial-gradient(ellipse at 50% 0%, rgba(91,138,245,0.08) 0%, transparent 60%)" }}>
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
               style={{ background: "linear-gradient(135deg, #5b8af5, #7c5bf5)" }}>
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M6 20.25h12m-7.5-3v3m3-3v3m-10.125-3h17.25c.621 0 1.125-.504 1.125-1.125V4.875C21 4.254 20.496 3.75 19.875 3.75H4.125C3.504 3.75 3 4.254 3 4.875v11.25c0 .621.504 1.125 1.125 1.125z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold">Tablo Web</h1>
          <p className="text-white/40 text-sm mt-1">Sign in with your Tablo account</p>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="text-xs font-medium text-white/50 uppercase tracking-wider mb-1.5 block">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoFocus
              className="w-full px-4 py-3 rounded-xl bg-surface-raised border border-surface-border
                         text-white placeholder-white/25 text-sm
                         focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent/50
                         transition"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-white/50 uppercase tracking-wider mb-1.5 block">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full px-4 py-3 rounded-xl bg-surface-raised border border-surface-border
                         text-white placeholder-white/25 text-sm
                         focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent/50
                         transition"
            />
          </div>

          {error && (
            <p className="text-red-400 text-sm px-1">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !email || !password}
            className="w-full py-3 rounded-xl font-semibold text-sm transition
                       disabled:opacity-40 disabled:cursor-not-allowed
                       hover:opacity-90 active:scale-[0.98]"
            style={{ background: "linear-gradient(135deg, #5b8af5, #7c5bf5)" }}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                Connecting…
              </span>
            ) : "Sign In"}
          </button>
        </form>

        <p className="text-center text-white/20 text-xs mt-8">
          Uses your Tablo account credentials · Runs entirely on your local network
        </p>
      </div>
    </div>
  );
}
