import { describe, it, expect } from "vitest";
import type { GuideChannel, GridChannel, Program } from "../api/tablo";

// ── replicated filter logic (mirrors ChannelGrid.tsx / GuideGridView.tsx) ──

type ContentFilter = "all" | "movies" | "sports" | "news" | "reality" | "documentary" | "ota" | "fast";

function matchesContentFilter(ch: GuideChannel, f: ContentFilter): boolean {
  if (f === "all") return true;
  if (f === "ota") return ch.kind === "ota";
  if (f === "fast") return ch.kind === "ott";
  const prog = ch.current_program;
  if (!prog) return false;
  const genres = prog.genres ?? [];
  if (f === "movies")      return prog.kind === "movieAiring";
  if (f === "sports")      return prog.kind === "sportEvent" || genres.some(g => /sport/i.test(g));
  if (f === "news")        return genres.some(g => /news/i.test(g));
  if (f === "reality")     return genres.some(g => /reality/i.test(g));
  if (f === "documentary") return genres.some(g => /documentary/i.test(g));
  return true;
}

function airingMatchesFilter(air: Program, f: ContentFilter): boolean {
  if (f === "all") return true;
  const genres = air.genres ?? [];
  if (f === "movies")      return air.kind === "movieAiring";
  if (f === "sports")      return air.kind === "sportEvent" || genres.some(g => /sport/i.test(g));
  if (f === "news")        return genres.some(g => /news/i.test(g));
  if (f === "reality")     return genres.some(g => /reality/i.test(g));
  if (f === "documentary") return genres.some(g => /documentary/i.test(g));
  return false;
}

function channelMatchesFilter(ch: GridChannel, f: ContentFilter): boolean {
  if (f === "all")  return true;
  if (f === "ota")  return ch.kind === "ota";
  if (f === "fast") return ch.kind === "ott";
  return ch.airings.some(a => airingMatchesFilter(a, f));
}

// ── helpers ────────────────────────────────────────────────────────────────

function makeGuide(kind: string, program?: Partial<Program>): GuideChannel {
  return {
    identifier: "test",
    call_sign: "TEST",
    major: 1,
    minor: 1,
    network: "Test",
    kind,
    display_name: "Test Channel",
    logo_url: null,
    current_program: program
      ? { title: "Test Show", description: null, start: new Date().toISOString(), duration: 3600, ...program }
      : null,
  };
}

function makeGrid(kind: string, airings: Partial<Program>[] = []): GridChannel {
  return {
    identifier: "test",
    call_sign: "TEST",
    major: 1,
    minor: 1,
    network: "Test",
    kind,
    display_name: "Test Channel",
    logo_url: null,
    airings: airings.map(a => ({
      title: "Test", description: null,
      start: new Date().toISOString(), duration: 3600, ...a,
    })),
  };
}

// ── Live TV filter tests ────────────────────────────────────────────────────

describe("matchesContentFilter (Live TV)", () => {
  it("all passes everything", () => {
    expect(matchesContentFilter(makeGuide("ota"), "all")).toBe(true);
    expect(matchesContentFilter(makeGuide("ott"), "all")).toBe(true);
  });

  it("ota matches only ota channels", () => {
    expect(matchesContentFilter(makeGuide("ota"), "ota")).toBe(true);
    expect(matchesContentFilter(makeGuide("ott"), "ota")).toBe(false);
  });

  it("fast matches only ott channels", () => {
    expect(matchesContentFilter(makeGuide("ott"), "fast")).toBe(true);
    expect(matchesContentFilter(makeGuide("ota"), "fast")).toBe(false);
  });

  it("movies matches movieAiring kind", () => {
    expect(matchesContentFilter(makeGuide("ota", { kind: "movieAiring" }), "movies")).toBe(true);
    expect(matchesContentFilter(makeGuide("ota", { kind: "episode" }), "movies")).toBe(false);
  });

  it("sports matches sportEvent kind", () => {
    expect(matchesContentFilter(makeGuide("ota", { kind: "sportEvent" }), "sports")).toBe(true);
  });

  it("sports matches Sports genre", () => {
    expect(matchesContentFilter(makeGuide("ota", { genres: ["Sports"] }), "sports")).toBe(true);
  });

  it("news matches News genre", () => {
    expect(matchesContentFilter(makeGuide("ota", { genres: ["News"] }), "news")).toBe(true);
    expect(matchesContentFilter(makeGuide("ota", { genres: ["Comedy"] }), "news")).toBe(false);
  });

  it("reality matches Reality genre case-insensitively", () => {
    expect(matchesContentFilter(makeGuide("ota", { genres: ["Reality"] }), "reality")).toBe(true);
    expect(matchesContentFilter(makeGuide("ota", { genres: ["reality tv"] }), "reality")).toBe(true);
  });

  it("documentary matches Documentary genre", () => {
    expect(matchesContentFilter(makeGuide("ota", { genres: ["Documentary"] }), "documentary")).toBe(true);
  });

  it("returns false when program is null for content filters", () => {
    expect(matchesContentFilter(makeGuide("ota"), "movies")).toBe(false);
    expect(matchesContentFilter(makeGuide("ota"), "news")).toBe(false);
  });
});

// ── Guide Grid filter tests ─────────────────────────────────────────────────

describe("channelMatchesFilter (Guide Grid)", () => {
  it("all passes everything", () => {
    expect(channelMatchesFilter(makeGrid("ota"), "all")).toBe(true);
  });

  it("ota / fast filter by channel kind", () => {
    expect(channelMatchesFilter(makeGrid("ota"), "ota")).toBe(true);
    expect(channelMatchesFilter(makeGrid("ott"), "fast")).toBe(true);
    expect(channelMatchesFilter(makeGrid("ota"), "fast")).toBe(false);
  });

  it("movies matches if any airing is movieAiring", () => {
    const ch = makeGrid("ota", [{ kind: "episode" }, { kind: "movieAiring" }]);
    expect(channelMatchesFilter(ch, "movies")).toBe(true);
  });

  it("no match if no airings have the right genre", () => {
    const ch = makeGrid("ota", [{ kind: "episode", genres: ["Comedy"] }]);
    expect(channelMatchesFilter(ch, "news")).toBe(false);
  });
});
