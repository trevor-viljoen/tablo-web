import { useState, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "./api/tablo";
import { LoginScreen } from "./components/LoginScreen";
import { ChannelGrid } from "./components/ChannelGrid";

const qc = new QueryClient();

function Inner() {
  const [authed, setAuthed] = useState<boolean | null>(null);

  const check = async () => {
    try {
      const s = await api.status();
      setAuthed(s.authenticated);
    } catch {
      setAuthed(false);
    }
  };

  useEffect(() => { check(); }, []);

  const logout = async () => {
    await api.logout().catch(() => {});
    qc.clear();
    setAuthed(false);
  };

  if (authed === null) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-accent border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!authed) return <LoginScreen onSuccess={() => setAuthed(true)} />;

  return <ChannelGrid onLogout={logout} />;
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <Inner />
    </QueryClientProvider>
  );
}
