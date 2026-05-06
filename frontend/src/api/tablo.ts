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
  stream_url: string;
  transcoded?: boolean;
}

export interface Program {
  title: string | null;
  description: string | null;
  start: string;
  duration: number;
}

export interface GuideChannel {
  identifier: string;
  call_sign: string;
  major: number;
  minor: number;
  network: string;
  kind: string;
  display_name: string;
  logo_url: string | null;
  current_program: Program | null;
}

export interface GridChannel extends Omit<GuideChannel, 'current_program'> {
  airings: Program[];
}

export interface Recording {
  identifier: number;
  path: string;
  title: string | null;
  description: string | null;
  start: string;
  duration: number;
  thumbnail: string | null;
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

  guide: () => req<GuideChannel[]>("/channels/guide"),
  
  guideGrid: () => req<GridChannel[]>("/channels/guide-grid"),

  library: () => req<Recording[]>("/channels/library"),

  startStream: (identifier: string, transcode?: boolean) => {
    let url = `/stream/${identifier}`;
    if (transcode !== undefined) {
      url += `?transcode=${transcode}`;
    }
    return req<StreamStart>(url, { method: "POST" });
  },

  stopStream: (sessionId: string) =>
    req<{ ok: boolean }>(`/stream/${sessionId}`, { method: "DELETE" }),
};
