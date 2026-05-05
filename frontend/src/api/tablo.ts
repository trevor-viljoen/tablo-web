const BASE = "/api";

export interface AuthStatus {
  authenticated: boolean;
  devices: { sid: string; name: string }[];
  active_sid: string | null;
}

export interface Channel {
  identifier: string;
  call_sign: string;
  major: number;
  minor: number;
  network: string;
  kind: string;
  display_name: string;
}

export interface StreamStart {
  session_id: string;
  proxy_url: string;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}

export const api = {
  status: () => req<AuthStatus>("/auth/status"),

  login: (email: string, password: string) =>
    req<{ devices: { sid: string; name: string }[]; active_sid: string | null }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) }
    ),

  selectDevice: (sid: string) =>
    req<{ sid: string; name: string }>(`/auth/device/${sid}`, { method: "POST" }),

  logout: () => req<{ ok: boolean }>("/auth/logout", { method: "DELETE" }),

  channels: (refresh = false) =>
    req<Channel[]>(`/channels${refresh ? "?refresh=true" : ""}`),

  startStream: (identifier: string) =>
    req<StreamStart>(`/stream/${identifier}`, { method: "POST" }),

  stopStream: (sessionId: string) =>
    req<{ ok: boolean }>(`/stream/${sessionId}`, { method: "DELETE" }),
};
