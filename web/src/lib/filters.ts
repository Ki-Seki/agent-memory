// Which memories the list shows. Each filter but Added holds any number of values: a memory has to match
// one of them, and pass every filter that is on. Added holds one choice: a preset or a date range.
import { DAY, localDay, ymd } from "./format";
import type { Memory, MemoryType, Place } from "./types";

export const TYPES: MemoryType[] = ["feedback", "reference", "project", "user"];
export const TYPE_HELP: Record<MemoryType, string> = {
  user: "Who you are",
  feedback: "How you want work done",
  project: "Facts about a project",
  reference: "Where to find things",
};
export const ADDED: [string, string][] = [["today", "Today"], ["7", "Past 7 days"], ["30", "Past 30 days"], ["90", "Past 3 months"], ["365", "Past year"]];
export const STATUS: [string, string][] = [["tidy", "Needs tidying"], ["stale", "Unchanged 60+ days"]];
export const SORTS: [Sort, string][] = [["new", "Newest first"], ["old", "Oldest first"], ["edited", "Recently changed"], ["az", "A to Z"]];
export type Sort = "new" | "old" | "edited" | "az";

export type ListKey = "type" | "loads" | "tool" | "kw" | "status";
export interface Filters { type: string[]; loads: string[]; tool: string[]; kw: string[]; status: string[]; added: string }
export const noFilters = (): Filters => ({ type: [], loads: [], tool: [], kw: [], status: [], added: "" });
export const activeCount = (f: Filters) => (["type", "loads", "tool", "kw", "status"] as ListKey[]).filter((k) => f[k].length).length + (f.added ? 1 : 0);

export const touched = (m: Memory) => m.updated || m.created || "";
export const stale = (m: Memory) => Date.now() - (Date.parse(touched(m)) || Date.now()) >= 60 * DAY;

const TEST: Record<ListKey, (m: Memory, v: string, kw: Set<string>) => boolean> = {
  type: (m, v) => m.type === v,
  loads: (m, v) => (v === "global" ? m.scope === "global" : m.scope === "here" && m.place === v.slice(6)),
  tool: (m, v) => m.tool === v,
  kw: (_m, v, terms) => terms.has(v),
  status: (m, v) => (v === "tidy" ? m.issues.length > 0 : stale(m)),
};

export function addedOk(m: Memory, added: string): boolean {
  if (!added) return true;
  const d = localDay(m.created);
  if (!d) return false;
  if (added === "today") return d === ymd(new Date());
  if (added.startsWith("range:")) {
    const [, from, to] = added.split(":");
    return (!from || d >= from) && (!to || d <= to);
  }
  return Date.now() - Date.parse(m.created) <= Number(added) * DAY;
}

/** Whether m passes the filters; skip leaves one filter out, to count what its options would show. */
export function passes(m: Memory, f: Filters, terms: Set<string>, skip?: ListKey | "added"): boolean {
  for (const key of Object.keys(TEST) as ListKey[]) {
    if (key !== skip && f[key].length && !f[key].some((v) => TEST[key](m, v, terms))) return false;
  }
  return skip === "added" || addedOk(m, f.added);
}

export interface Option { value: string; label: string; count: number }
export interface ListFilter { key: ListKey; label: string; any: string; options: Option[]; search?: boolean }

/** Every list filter with its options and how many memories each would show alongside the other filters. */
export function listFilters(M: Memory[], places: Place[], f: Filters, termSets: Map<string, Set<string>>, kwName: Map<string, string>): ListFilter[] {
  const count = (key: ListKey, v: string) => M.filter((m) => passes(m, f, termSets.get(m.id)!, key) && TEST[key](m, v, termSets.get(m.id)!)).length;
  const opts = (key: ListKey, list: [string, string][]): Option[] => list.map(([value, label]) => ({ value, label, count: count(key, value) }));
  const tools = [...new Set(M.map((m) => m.tool).filter(Boolean))].sort();
  const kwCounts = new Map<string, number>();
  for (const m of M) if (passes(m, f, termSets.get(m.id)!, "kw")) for (const t of termSets.get(m.id)!) if (kwName.has(t)) kwCounts.set(t, (kwCounts.get(t) || 0) + 1);
  const keywords = [...kwCounts].filter(([, c]) => c >= 2).sort((a, b) => b[1] - a[1] || kwName.get(a[0])!.localeCompare(kwName.get(b[0])!)).slice(0, 80);
  for (const k of f.kw) if (!keywords.some(([x]) => x === k)) keywords.unshift([k, kwCounts.get(k) || 0]);
  return [
    { key: "type", label: "Type", any: "All", options: opts("type", TYPES.map((t) => [t, t])) },
    { key: "loads", label: "Loads in", any: "Anywhere", options: opts("loads", [["global", "Everywhere"], ...places.map((p): [string, string] => ["place:" + p.key, p.key])]) },
    ...(tools.length > 1 ? [{ key: "tool" as const, label: "Source", any: "Any", options: opts("tool", tools.map((t): [string, string] => [t, t])) }] : []),
    { key: "kw", label: "Keyword", any: "Any", search: true, options: keywords.map(([value, n]) => ({ value, label: kwName.get(value) || value, count: n })) },
    { key: "status", label: "Status", any: "Any", options: opts("status", STATUS) },
  ];
}

export function addedOptions(M: Memory[], f: Filters, termSets: Map<string, Set<string>>): Option[] {
  return ADDED.map(([value, label]) => ({ value, label, count: M.filter((m) => passes(m, f, termSets.get(m.id)!, "added") && addedOk(m, value)).length }));
}
