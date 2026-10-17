import { touched } from "./filters";
import type { Memory } from "./types";

export const terms = (text: string) => text.toLowerCase().split(/\s+/).filter(Boolean);

/** Memories containing every word, best first: words in the description count most. */
export function lexical(M: Memory[], query: string): number[] {
  const ts = terms(query);
  if (!ts.length) return [];
  const scored: [number, number][] = [];
  M.forEach((m, i) => {
    const desc = m.description.toLowerCase();
    const hay = `${desc}\n${m.body.toLowerCase()}\n${(m.place || "").toLowerCase()}\n${m.id}\n${m.type}`;
    if (!ts.every((t) => hay.includes(t))) return;
    scored.push([ts.reduce((s, t) => s + (desc.includes(t) ? 10 : 0) + Math.min(5, hay.split(t).length - 1), 0), i]);
  });
  return scored.sort((a, b) => b[0] - a[0] || touched(M[b[1]]).localeCompare(touched(M[a[1]]))).map(([, i]) => i);
}

/** A line of the body around the first word the description lacks, or null when the description has them all. */
export function snippet(m: Memory, ts: string[]): string | null {
  const desc = m.description.toLowerCase();
  if (ts.every((t) => desc.includes(t))) return null;
  const body = m.body.replace(/\s+/g, " ");
  const lower = body.toLowerCase();
  const at = ts.filter((t) => !desc.includes(t)).map((t) => lower.indexOf(t)).filter((k) => k >= 0).sort((a, b) => a - b)[0];
  if (at == null) return null;
  const start = Math.max(0, at - 50);
  return (start ? "…" : "") + body.slice(start, start + 160);
}

/** Text split into plain and matched parts, for <mark>. */
export function marks(text: string, ts: string[]): { text: string; hit: boolean }[] {
  const words = ts.filter((t) => t.length > 1 || /[㐀-鿿]/.test(t));
  if (!words.length) return [{ text, hit: false }];
  const re = new RegExp(`(${words.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return text.split(re).map((part, i) => ({ text: part, hit: i % 2 === 1 })).filter((p) => p.text);
}
