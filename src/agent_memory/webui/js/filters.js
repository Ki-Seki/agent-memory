// Which memories the list shows. Each filter but Added holds any number of values: a memory has to match
// one of them, and pass every filter that is on. Added holds one choice: a preset or a date range.
import { DAY, localDay, ymd } from "./format.js";

export const TYPES = ["feedback", "reference", "project", "user"];
export const TYPE_HELP = {
  user: "Who you are",
  feedback: "How you want work done",
  project: "Facts about a project",
  reference: "Where to find things",
};
export const ADDED = [["today", "Today"], ["7", "Past 7 days"], ["30", "Past 30 days"], ["90", "Past 3 months"], ["365", "Past year"]];
export const STATUS = [["tidy", "Needs tidying"], ["stale", "Unchanged 60+ days"]];
export const SORTS = [["new", "Newest first"], ["old", "Oldest first"], ["edited", "Recently changed"], ["az", "A to Z"]];
export const LISTS = ["type", "loads", "tool", "kw", "status"];

export const noFilters = () => ({ type: [], loads: [], tool: [], kw: [], status: [], added: "" });
export const activeCount = (f) => LISTS.filter((k) => f[k].length).length + (f.added ? 1 : 0);

export const touched = (m) => m.updated || m.created || "";
export const stale = (m) => Date.now() - (Date.parse(touched(m)) || Date.now()) >= 60 * DAY;

const TEST = {
  type: (m, v) => m.type === v,
  loads: (m, v) => (v === "global" ? m.scope === "global" : m.scope === "here" && m.place === v.slice(6)),
  tool: (m, v) => m.tool === v,
  kw: (_m, v, terms) => terms.has(v),
  status: (m, v) => (v === "tidy" ? m.issues.length > 0 : stale(m)),
};

export function addedOk(m, added) {
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
export function passes(m, f, terms, skip) {
  for (const key of LISTS) {
    if (key !== skip && f[key].length && !f[key].some((v) => TEST[key](m, v, terms))) return false;
  }
  return skip === "added" || addedOk(m, f.added);
}

/** Every list filter with its options and how many memories each would show alongside the other filters. */
export function listFilters(M, places, f, termSets, kwName) {
  const count = (key, v) => M.filter((m) => passes(m, f, termSets.get(m.id), key) && TEST[key](m, v, termSets.get(m.id))).length;
  const opts = (key, list) => list.map(([value, label]) => ({ value, label, count: count(key, value) }));
  const tools = [...new Set(M.map((m) => m.tool).filter(Boolean))].sort();
  const kwCounts = new Map();
  for (const m of M) if (passes(m, f, termSets.get(m.id), "kw")) for (const t of termSets.get(m.id)) if (kwName.has(t)) kwCounts.set(t, (kwCounts.get(t) || 0) + 1);
  const keywords = [...kwCounts].filter(([, c]) => c >= 2).sort((a, b) => b[1] - a[1] || kwName.get(a[0]).localeCompare(kwName.get(b[0]))).slice(0, 80);
  for (const k of f.kw) if (!keywords.some(([x]) => x === k)) keywords.unshift([k, kwCounts.get(k) || 0]);
  return [
    { key: "type", label: "Type", any: "All", options: opts("type", TYPES.map((t) => [t, t])) },
    { key: "loads", label: "Loads in", any: "Anywhere", options: opts("loads", [["global", "Everywhere"], ...places.map((p) => ["place:" + p.key, p.key])]) },
    ...(tools.length > 1 ? [{ key: "tool", label: "Source", any: "Any", options: opts("tool", tools.map((t) => [t, t])) }] : []),
    { key: "kw", label: "Keyword", any: "Any", search: true, options: keywords.map(([value, n]) => ({ value, label: kwName.get(value) || value, count: n })) },
    { key: "status", label: "Status", any: "Any", options: opts("status", STATUS) },
  ];
}

export function addedOptions(M, f, termSets) {
  return ADDED.map(([value, label]) => ({ value, label, count: M.filter((m) => passes(m, f, termSets.get(m.id), "added") && addedOk(m, value)).length }));
}
