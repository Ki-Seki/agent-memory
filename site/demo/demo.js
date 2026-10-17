// The live demo: mem ui's own page, with this file answering its calls instead of a server. The answers
// come from snapshot.json (scripts/site.py saves it from the demo memories); changes are kept in this tab
// only, and every date moves so the newest memory is a day old, whenever the demo is opened.
import { ApiError, useTransport } from "./js/api.js";
import { app } from "./js/store.js";

const snap = await (await fetch("snapshot.json")).json();
const DATA = "~/agent-memory-data";
const DAY = 864e5;
const clone = (v) => structuredClone(v);

// ---------------------------------------------------------------- dates

const stamps = (m) => [m.created, m.updated].filter(Boolean);
const newest = Math.max(...snap.state.memories.flatMap(stamps).map(Date.parse));
const today = new Date(); today.setHours(0, 0, 0, 0);
const days = Math.floor((+today - newest) / DAY);  // the newest lands on yesterday (its time of day kept)
/** The same instant moved by whole days, written the way it was (date, time and offset). */
function shift(iso) {
  if (!iso || !days) return iso;
  const [, y, mo, d] = iso.match(/^(\d{4})-(\d{2})-(\d{2})/) ?? [];
  if (!y) return iso;
  const moved = new Date(Date.UTC(+y, mo - 1, +d) + days * DAY).toISOString().slice(0, 10);
  return moved + iso.slice(10);
}
const pad = (n) => String(n).padStart(2, "0");
function nowIso() {
  const d = new Date(), off = -d.getTimezoneOffset();
  const zone = `${off >= 0 ? "+" : "-"}${pad(Math.floor(Math.abs(off) / 60))}:${pad(Math.abs(off) % 60)}`;
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}${zone}`;
}

// ---------------------------------------------------------------- the memories, as files

const RESERVED = new Set(["true", "false", "null", "yes", "no", "on", "off", "~"]);
const quoted = (s) => s === "" || s !== s.trim() || s.includes("\n") || RESERVED.has(s.toLowerCase()) || /^[-?:,[\]{}#&*!|>'"%@`]/.test(s)
  || s.includes(": ") || s.includes(" #") || s.endsWith(":") || /^[-+]?\d+(\.\d+)?$/.test(s);
const emit = (v) => (Array.isArray(v) ? `[${v.map(emit).join(", ")}]` : typeof v === "string" ? (quoted(v) ? JSON.stringify(v) : v) : String(v));
/** The file as the hooks write it: frontmatter, then the memory. */
function file(meta, body) {
  const lines = Object.entries(meta).flatMap(([k, v]) =>
    v && typeof v === "object" && !Array.isArray(v) ? [`${k}:`, ...Object.entries(v).map(([kk, vv]) => `  ${kk}: ${emit(vv)}`)] : [`${k}: ${emit(v)}`]);
  return `---\n${lines.join("\n")}\n---\n${body.trimEnd()}\n`;
}

/** What `mem lint` would say about a memory. */
function lint(m, names) {
  const out = [];
  const desc = m.description.split(/\s+/).join(" ");
  if (desc.length > 150) out.push(`description is ${desc.length} characters; the index shows 150`);
  const text = m.body.trim();
  if (!text) return [...out, "body is empty"];
  if (text.length > 1500) out.push(`body is ${text.length.toLocaleString()} characters; keep it under about 1,500`);
  if (text.split("\n").find((l) => l.trim()).trimStart().startsWith("#")) out.push("opens with a heading instead of the fact");
  if (m.type === "feedback" || m.type === "project") {
    const missing = [["**Why:**", /\*\*\s*why\s*:?\s*\*\*/i], ["**How to apply:**", /\*\*\s*how to apply\s*:?\s*\*\*/i]].filter(([, rx]) => !rx.test(m.body)).map(([l]) => l);
    if (missing.length) out.push("no " + missing.join(" or "));
  }
  const broken = [...new Set([...m.body.matchAll(/\[\[([^\]]+)\]\]/g)].map((x) => x[1].trim()))].filter((n) => !names.has(n)).sort();
  if (broken.length) out.push(`links to ${broken.map((n) => `[[${n}]]`).join(", ")}, which no memory is named`);
  return out;
}

const hash = () => Math.random().toString(16).slice(2, 18).padEnd(16, "0");
const PLACE_FIELDS = ["cwd", "git_root", "git_remote", "git_branch"];
const placeKey = (src) => src.git_remote || src.git_root || src.cwd || "";

let memories = snap.state.memories.map((m) => {
  const meta = clone(m.meta);
  for (const k of ["created", "updated"]) if (meta[k]) meta[k] = shift(meta[k]);
  let raw = m.raw;
  for (const k of ["created", "updated"]) if (m.meta[k]) raw = raw.replace(`${k}: ${m.meta[k]}`, `${k}: ${meta[k]}`);
  return {
    ...m, meta, raw, created: shift(m.created), updated: shift(m.updated),
    near: m.similar.map((s) => ({ id: snap.state.memories[s.i].id, s: s.s })),  // by id, as memories come and go
    allKeywords: m.keywords,
  };
});
let commits = snap.activity.commits.map((c) => ({ ...c, date: shift(c.date) }));
const before = new Map();  // commit → the memories as they were, for Undo
let stopwords = [];
let autoUpdates = true;
let stamp = 0;

function refresh(m) {
  m.raw = file(m.meta, m.body);
  m.hash = hash();
  m.issues = lint(m, new Set(memories.map((x) => String(x.meta.name ?? ""))));
}

function state() {
  const at = new Map(memories.map((m, i) => [m.id, i]));
  const places = snap.state.places
    .map((p) => ({ ...p, count: memories.filter((m) => m.scope === "here" && m.place === p.key).length }))
    .filter((p) => p.count);
  const words = new Set(stopwords);
  return {
    ...snap.state, places, stamp: String(stamp), sync: { remote: true, ahead: 0 },
    memories: memories.map(({ near, allKeywords, ...m }) => ({
      ...m,
      similar: near.filter((x) => at.has(x.id)).map((x) => ({ i: at.get(x.id), s: x.s })),
      keywords: allKeywords.filter((k) => !words.has(k.k) && !words.has(k.t.toLowerCase())),
    })),
  };
}

function record(subject, counts) {
  const sha = hash().slice(0, 10);
  before.set(sha, clone(memories));
  commits.unshift({ sha, date: nowIso(), subject, tool: "ui", added: 0, changed: 0, deleted: 0, ...counts });
  stamp++;
  return sha;
}

function placeCtx(place) {
  if (place?.path) throw new ApiError("The demo cannot see folders on your computer; pick one of the places listed.", 400);
  const p = snap.state.places.find((x) => x.key === (place?.key ?? place));
  if (!p) throw new ApiError("Pick a place from the list or type a folder path.", 400);
  return p.ctx;
}

function find(id, base) {
  const m = memories.find((x) => x.id === id);
  if (!m) throw new ApiError("That memory no longer exists; it may have been deleted elsewhere.", 404);
  if (base && m.hash !== base) throw new ApiError("This memory changed after you opened it. Close it and open it again to see the new version.", 409);
  return m;
}

// ---------------------------------------------------------------- the calls the page makes

const settings = () => ({ ...snap.settings, keywordStopwords: stopwords });
const update = () => {
  const v = snap.settings.version;
  return { current: v, latest: v, available: false, checked: nowIso(), auto: autoUpdates, method: "uv-tool", command: "uv tool upgrade agent-memory-git && mem install", oneClick: true };
};

const GET = {
  "/api/state": state,
  "/api/stamp": () => ({ stamp: String(stamp) }),
  "/api/activity": () => ({ commits }),
  "/api/index-preview": (q) => {
    const preview = snap.previews[q.get("place") ?? ""];
    if (!preview) throw new ApiError("unknown place", 404);
    return preview;
  },
  "/api/settings": settings,
  "/api/doctor": () => snap.doctor,
  "/api/update": update,
  "/api/search": async (q) => {
    await new Promise((ok) => setTimeout(ok, 250));  // about as long as the model takes
    return snap.search[(q.get("q") ?? "").trim()] ?? { hits: [], semantic: true };
  },
};

const POST = {
  "/api/create": (p) => {
    if (!["user", "feedback", "project", "reference"].includes(p.type) || !["global", "here"].includes(p.scope)) throw new ApiError("Pick a type and where the memory loads.", 400);
    const description = String(p.description ?? "").split(/\s+/).filter(Boolean).join(" ");
    if (!description) throw new ApiError("A memory needs a one-line description.", 400);
    const source = { tool: "ui", host: "demo" };
    if (p.scope === "here") {
      if (!p.place) throw new ApiError("Pick the place where this memory should load.", 400);
      const ctx = placeCtx(p.place);
      for (const k of PLACE_FIELDS) if (ctx[k]) source[k] = ctx[k];
    }
    const name = description.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40).replace(/-$/, "") || "note";
    const created = nowIso();
    const id = `${created.slice(0, 10).replaceAll("-", "")}-${name}-${hash().slice(0, 4)}`;
    const meta = { id, name, type: p.type, scope: p.scope, description, created, source };
    const rel = `${id.slice(0, 4)}/${id.slice(4, 6)}/${id}.md`;
    const m = { id, rel, path: `${DATA}/memories/${rel}`, meta, body: String(p.body ?? ""), description, type: p.type, scope: p.scope,
      place: p.scope === "here" ? placeKey(source) : "", tool: "ui", host: "demo", created, updated: "", near: [], allKeywords: [], terms: [] };
    const commit = record(`memory: add ${id} (ui)`, { added: 1 });
    memories.push(m);
    refresh(m);
    return { id, commit };
  },
  "/api/edit": (p) => {
    const m = find(p.id, p.base), c = p.change ?? {}, changed = [];
    const next = clone(m.meta);
    for (const key of ["type", "scope"]) if (key in c && c[key] !== next[key]) { next[key] = c[key]; changed.push(key); }
    if ("description" in c) {
      const d = String(c.description).split(/\s+/).filter(Boolean).join(" ");
      if (!d) throw new ApiError("A memory needs a one-line description.", 400);
      if (d !== next.description) { next.description = d; changed.push("description"); }
    }
    let body = m.body;
    if ("body" in c && String(c.body).trimEnd() !== m.body.trimEnd()) { body = String(c.body); changed.push("body"); }
    const source = { ...(next.source ?? {}) };
    if (c.place && next.scope === "here") {
      const ctx = placeCtx(c.place);
      for (const k of PLACE_FIELDS) delete source[k];
      for (const k of PLACE_FIELDS) if (ctx[k]) source[k] = ctx[k];
      changed.push("place");
    }
    if (next.scope === "here" && !(source.cwd || source.git_remote)) throw new ApiError("Pick the place where this memory should load.", 400);
    if (!changed.length) return { id: m.id, commit: null };
    const commit = record(`memory: edit ${m.id} (${changed.join(", ")}) (ui)`, { changed: 1 });
    if (changed.length) next.updated = nowIso();
    delete next.source;
    next.source = source;  // provenance stays last, as the hooks write it
    Object.assign(m, { meta: next, body, description: next.description, type: next.type, scope: next.scope, updated: next.updated, place: next.scope === "here" ? placeKey(source) : "" });
    refresh(m);
    return { id: m.id, commit };
  },
  "/api/delete": (p) => {
    const items = Array.isArray(p.items) ? p.items : [p];
    const gone = items.map((it) => find(it.id, it.base));  // all or nothing
    const commit = record(gone.length === 1 ? `memory: delete ${gone[0].id} (ui)` : `memory: delete ${gone.length} memories (ui)`, { deleted: gone.length });
    memories = memories.filter((m) => !gone.includes(m));
    return { commit };
  },
  "/api/undo": (p) => {
    const was = before.get(p.commit);
    if (!was) throw new ApiError("Only changes made on this page can be undone here.", 400);
    record(`memory: undo ${p.commit} (ui)`, { changed: 1 });
    memories = clone(was);
    return { ok: true };
  },
  "/api/settings": (p) => {
    if ("keyword_stopwords" in p) stopwords = [...new Set(p.keyword_stopwords.map((w) => w.trim().toLowerCase()).filter(Boolean))].sort();
    if ("check_updates" in p) autoUpdates = !!p.check_updates;
    stamp++;
    return settings();
  },
  "/api/sync": () => ({ ok: true, sync: { remote: true, ahead: 0 } }),
  "/api/update/check": update,
  "/api/update": () => ({ ok: true, changed: false }),
};

useTransport(async (path, body) => {
  const url = new URL(path, location.href);
  const fn = (body === undefined ? GET : POST)[url.pathname];
  if (!fn) throw new ApiError("not found", 404);
  return clone(await fn(body === undefined ? url.searchParams : body));
});
if (!new URLSearchParams(location.search).has("shot")) app.demo = { queries: snap.queries };  // ?shot: as mem ui looks, for screenshots
await import("./js/main.js");
