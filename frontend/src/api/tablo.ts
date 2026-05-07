const BASE = "/api";

export interface AuthStatus {
  authenticated: boolean;
  email: string | null;
  devices: { sid: string; name: string }[];
  active_sid: string | null;
}

export interface DebugReport {
  generated_at: string;
  server: { python: string; platform: string; arch: string };
  auth: { authenticated: boolean; device_count: number; active_device_name: string | null; active_device_sid: string | null };
  active_streams: number;
  recent_logs: string[];
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
  genres?: string[];
  kind?: string | null;
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

async function* ndjsonStream<T>(path: string, signal?: AbortSignal): AsyncGenerator<T> {
  const res = await fetch(BASE + path, { signal });
  if (!res.ok || !res.body) throw new Error(res.statusText);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line.trim()) yield JSON.parse(line) as T;
      }
    }
    if (buffer.trim()) yield JSON.parse(buffer) as T;
  } finally {
    reader.cancel();
  }
}

function guideStream(signal?: AbortSignal) {
  return ndjsonStream<GuideChannel>("/channels/guide/stream", signal);
}

function guideGridStream(signal?: AbortSignal) {
  return ndjsonStream<GridChannel>("/channels/guide-grid/stream", signal);
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

  debugReport: () => req<DebugReport>("/channels/debug-report"),

  channels: (refresh = false) =>
    req<Channel[]>(`/channels${refresh ? "?refresh=true" : ""}`),

  guide: () => req<GuideChannel[]>("/channels/guide"),
  guideStream: (signal?: AbortSignal) => guideStream(signal),
  guideGridStream: (signal?: AbortSignal) => guideGridStream(signal),
  
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
