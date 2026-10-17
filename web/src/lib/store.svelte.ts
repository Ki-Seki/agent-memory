// Everything the page knows and does, in one place: the memories, what the list shows, what is open,
// and the calls that change memories. Components read from `app` and call its methods.
import { MediaQuery, SvelteSet } from "svelte/reactivity";
import { api, token } from "./api";
import { activeCount, listFilters, noFilters, passes, touched, type Filters, type ListKey, type Sort } from "./filters";
import { plural } from "./format";
import { lexical } from "./search";
import type { Memory, MemoryType, Scope, State, UpdateResult, UpdateStatus } from "./types";

export type Page = "memories" | "insights" | "settings";
export type Theme = "system" | "light" | "dark";
export type Mode = "view" | "edit" | "new";

export interface Draft { description: string; type: MemoryType; scope: Scope; place: string; pathMode: boolean; path: string; body: string }
interface Toast { id: number; text: string; error?: boolean; undo?: string }
interface Ask { title: string; body?: string; action: string; danger?: boolean; resolve: (ok: boolean) => void }

const local = {
  get<T>(k: string, d: T): T {
    try { const v = localStorage.getItem("mem-ui-" + k); return v == null ? d : (JSON.parse(v) as T); } catch { return d; }
  },
  set(k: string, v: unknown) {
    try { localStorage.setItem("mem-ui-" + k, JSON.stringify(v)); } catch { /* private window */ }
  },
};

function pick<T extends string>(value: unknown, allowed: T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

const SORTERS: Record<Sort, (a: Memory, b: Memory) => number> = {
  new: (a, b) => (b.created || "").localeCompare(a.created || ""),
  old: (a, b) => (a.created || "").localeCompare(b.created || ""),
  edited: (a, b) => touched(b).localeCompare(touched(a)),
  az: (a, b) => a.description.localeCompare(b.description),
};

class App {
  data = $state<State | null>(null);
  bootError = $state("");
  page = $state<Page>("memories");
  openId = $state<string | null>(null);
  mode = $state<Mode>("view");
  draft = $state<Draft | null>(null);
  private base = "";
  q = $state("");
  sem = $state<{ id: string; score: number }[]>([]);
  semPending = $state(false);
  filters = $state<Filters>(noFilters());
  // saved choices are checked, since an older page on the same address may have stored other values
  sort = $state<Sort>(pick(local.get("sort", ""), ["new", "old", "edited", "az"], "new"));
  theme = $state<Theme>(pick(local.get("theme", ""), ["system", "light", "dark"], "system"));
  picked = new SvelteSet<string>();
  cursor = $state(-1);
  toasts = $state<Toast[]>([]);
  asking = $state<Ask | null>(null);
  update = $state<UpdateStatus | null>(null);
  updating = $state<"" | "upgrading" | "restarting">("");
  /** Wide enough for the list and the open memory side by side. */
  wide = new MediaQuery("min-width: 1024px");
  /** The list's width beside an open memory, once dragged; null keeps the width for the window size. */
  listWidth = $state<number | null>(local.get<number | null>("list-width", null));

  M = $derived(this.data?.memories ?? []);
  byId = $derived(new Map(this.M.map((m) => [m.id, m])));
  byName = $derived(new Map(this.M.map((m) => [String(m.meta?.name ?? ""), m])));
  termSets = $derived(new Map(this.M.map((m) => [m.id, new Set(m.terms)])));
  kwName = $derived(new Map(this.M.flatMap((m) => m.keywords.map((k): [string, string] => [k.k, k.t]))));
  open = $derived(this.openId ? (this.byId.get(this.openId) ?? null) : null);
  places = $derived(this.data?.places ?? []);
  filterDefs = $derived(listFilters(this.M, this.places, this.filters, this.termSets, this.kwName));
  filtering = $derived(activeCount(this.filters));

  /** The list: word matches (or every memory, sorted), then memories close in meaning that matched no word. */
  groups = $derived.by(() => {
    const ok = (m: Memory) => passes(m, this.filters, this.termSets.get(m.id)!);
    if (!this.q.trim()) return [{ title: null as string | null, items: this.M.filter(ok).sort(SORTERS[this.sort] ?? SORTERS.new) }];
    const lex = lexical(this.M, this.q).map((i) => this.M[i]).filter(ok);
    const seen = new Set(lex.map((m) => m.id));
    const sem = this.sem.map((h) => this.byId.get(h.id)).filter((m): m is Memory => !!m && !seen.has(m.id) && ok(m)).slice(0, 8);
    return [{ title: null, items: lex }, ...(sem.length ? [{ title: "Close in meaning", items: sem }] : [])];
  });
  rows = $derived(this.groups.flatMap((g) => g.items));
  countText = $derived.by(() => {
    if (this.q.trim()) {
      const [words, meaning] = this.groups;
      return `${plural(words.items.length, "match", "matches")}${meaning ? ` · ${meaning.items.length} close in meaning` : ""}${this.semPending ? " · searching by meaning…" : ""}`;
    }
    return this.rows.length === this.M.length ? plural(this.M.length, "memory", "memories") : `${this.rows.length} of ${this.M.length}`;
  });
  unpushed = $derived(this.data?.sync?.remote ? (this.data.sync.ahead ?? 0) : 0);

  // ------------------------------------------------------------ loading and routing

  async start() {
    if (!token) { this.bootError = "Open this page with the link that `mem ui` prints."; return; }
    this.readRoute();
    addEventListener("hashchange", () => this.readRoute());
    try { await this.reload(); }
    catch (e) {
      const err = e as Error & { status?: number };
      this.bootError = err.status === 401 ? "This link has expired. Run `mem ui` again and use the new link." : `Could not load memories: ${err.message}`;
      return;
    }
    this.refreshUpdate();  // checks PyPI at most once a day, unless turned off
    // memories that agents write while the page is open
    setInterval(async () => {
      if (document.hidden || !this.data || this.mode !== "view") return;
      try { const st = await api<{ stamp: string }>("/api/stamp"); if (st.stamp !== this.data.stamp) await this.reload(); } catch { /* server stopped */ }
    }, 20000);
  }
  async reload() {
    this.data = await api<State>("/api/state");
    for (const id of this.picked) if (!this.byId.has(id)) this.picked.delete(id);
    if (this.openId && !this.byId.has(this.openId) && this.mode !== "new") { this.openId = null; this.mode = "view"; }
    this.filters.loads = this.filters.loads.filter((v) => v === "global" || this.places.some((p) => "place:" + p.key === v));
  }
  private readRoute() {
    const [page, id] = location.hash.replace(/^#\/?/, "").split("/");
    this.page = page === "insights" || page === "settings" ? page : "memories";
    if (this.page === "memories" && id !== undefined) this.openId = decodeURIComponent(id) || null;
  }
  private writeRoute() {
    const hash = this.page === "memories" ? (this.openId ? `#/memories/${encodeURIComponent(this.openId)}` : "#/memories") : `#/${this.page}`;
    if (location.hash !== hash) history.replaceState(null, "", hash);
  }
  go(page: Page) { this.page = page; this.writeRoute(); scrollTo(0, 0); }

  // ------------------------------------------------------------ updates

  async refreshUpdate(force = false) {
    try { this.update = force ? await api<UpdateStatus>("/api/update/check", {}) : await api<UpdateStatus>("/api/update"); }
    catch { /* offline: say nothing */ }
  }
  async setAutoUpdate(on: boolean) {
    await api("/api/settings", { check_updates: on });
    await this.refreshUpdate(on);
  }
  /** Update with uv, then restart mem ui on the new code and reload the page once it answers. */
  async runUpdate(): Promise<UpdateResult> {
    this.updating = "upgrading";
    let r: UpdateResult;
    try { r = await api<UpdateResult>("/api/update", {}); }
    catch (e) { this.updating = ""; return { ok: false, error: (e as Error).message }; }
    if (!r.ok || !r.changed) {
      this.updating = "";
      if (r.ok) { this.toast("Already up to date"); await this.refreshUpdate(true); }
      return r;
    }
    this.updating = "restarting";
    try { await api("/api/restart", {}); } catch { /* the server may stop before it answers */ }
    const until = Date.now() + 60000;
    while (Date.now() < until) {
      await new Promise((ok) => setTimeout(ok, 800));
      try { await api("/api/stamp"); location.reload(); return r; } catch { /* not back yet */ }
    }
    this.updating = "";
    return { ...r, ok: false, error: `Updated to ${r.to}, but mem ui did not come back. Start it again in the terminal.` };
  }

  // ------------------------------------------------------------ preferences

  setTheme(v: Theme) { this.theme = v; local.set("theme", v); }
  setSort(v: Sort) { this.sort = v; local.set("sort", v); }
  setListWidth(v: number | null) { this.listWidth = v; local.set("list-width", v); }

  // ------------------------------------------------------------ search and filters

  private semTimer = 0;
  private semSeq = 0;
  search(text: string) {
    this.q = text;
    this.cursor = text.trim() ? 0 : -1;
    clearTimeout(this.semTimer);
    if (!text.trim()) { this.sem = []; this.semPending = false; return; }
    this.semPending = !!this.data?.semantic;
    if (!this.semPending) return;
    const seq = ++this.semSeq, query = text.trim();
    this.semTimer = window.setTimeout(async () => {
      try {
        const r = await api<{ hits: { id: string; score: number }[] }>(`/api/search?q=${encodeURIComponent(query)}`);
        if (seq === this.semSeq) this.sem = r.hits || [];
      } catch { /* word matches stay */ }
      if (seq === this.semSeq) this.semPending = false;
    }, 300);
  }
  setList(key: ListKey, values: string[]) { this.filters[key] = values; this.cursor = -1; }
  toggle(key: ListKey, v: string) { const cur = this.filters[key]; this.setList(key, cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v]); }
  setAdded(v: string) { this.filters.added = v; this.cursor = -1; }
  clearFilters() { this.filters = noFilters(); this.cursor = -1; }

  // ------------------------------------------------------------ open, edit, new

  private dirty() { return !!this.draft && JSON.stringify(this.draft) !== this.base; }
  private async leaveEdit(): Promise<boolean> {
    if (this.mode === "view" || !this.dirty()) return true;
    return this.ask({ title: "Discard your changes?", body: "What you typed in the form will be lost.", action: "Discard", danger: true });
  }
  async openMemory(id: string) {
    if (!(await this.leaveEdit())) return;
    this.mode = "view"; this.draft = null; this.openId = id;
    const k = this.rows.findIndex((m) => m.id === id);
    if (k >= 0) this.cursor = k;
    this.writeRoute();
  }
  async openByName(name: string) { const m = this.byName.get(name); if (m) await this.openMemory(m.id); }
  async close() {
    if (!(await this.leaveEdit())) return;
    this.mode = "view"; this.draft = null; this.openId = null;
    this.writeRoute();
  }
  async startNew() {
    if (!(await this.leaveEdit())) return;
    if (this.page !== "memories") this.go("memories");
    this.openId = null; this.mode = "new";
    this.draft = { description: "", type: "feedback", scope: "global", place: "", pathMode: false, path: "", body: "" };
    this.base = JSON.stringify(this.draft);
  }
  startEdit() {
    const m = this.open;
    if (!m) return;
    this.mode = "edit";
    this.draft = { description: m.description, type: m.type, scope: m.scope, place: m.scope === "here" ? m.place : "", pathMode: false, path: "", body: m.body };
    this.base = JSON.stringify(this.draft);
  }
  async cancelEdit() {
    if (!(await this.leaveEdit())) return;
    this.mode = "view"; this.draft = null;
    if (!this.openId) this.writeRoute();
  }
  /** Saves the form; returns an error message for the form, or "" when saved. */
  async save(): Promise<string> {
    const d = this.draft;
    if (!d) return "";
    if (!d.description.trim()) return "Add a one-line description.";
    let place: { key?: string; path?: string } | null = null;
    if (d.scope === "here") {
      if (d.pathMode) { if (!d.path.trim()) return "Type the folder path."; place = { path: d.path.trim() }; }
      else if (d.place) place = { key: d.place };
      else return "Choose where it loads.";
    }
    try {
      if (this.mode === "new") {
        const r = await api<{ id: string; commit: string }>("/api/create", { type: d.type, scope: d.scope, description: d.description, body: d.body, place });
        this.mode = "view"; this.draft = null;
        await this.reload();
        await this.openMemory(r.id);
        this.toast("Memory added", { undo: r.commit });
      } else {
        const m = this.open!;
        const change: Record<string, unknown> = {};
        if (d.description !== m.description) change.description = d.description;
        if (d.type !== m.type) change.type = d.type;
        if (d.scope !== m.scope) change.scope = d.scope;
        if (d.body !== m.body) change.body = d.body;
        if (place && (place.path || place.key !== m.place)) change.place = place;
        const r = await api<{ commit: string | null }>("/api/edit", { id: m.id, base: m.hash, change });
        this.mode = "view"; this.draft = null;
        await this.reload();
        if (r.commit) this.toast("Saved", { undo: r.commit });
      }
      return "";
    } catch (e) { return (e as Error).message; }
  }

  // ------------------------------------------------------------ delete, select, undo

  async remove(ids: string[]) {
    const ms = ids.map((id) => this.byId.get(id)).filter((m): m is Memory => !!m);
    if (!ms.length) return;
    const ok = await this.ask(ms.length === 1
      ? { title: "Delete this memory?", body: ms[0].description, action: "Delete", danger: true }
      : { title: `Delete ${ms.length} memories?`, body: ms.slice(0, 5).map((m) => `• ${m.description}`).join("\n") + (ms.length > 5 ? `\n…and ${ms.length - 5} more` : ""), action: `Delete ${ms.length}`, danger: true });
    if (!ok) return;
    try {
      const r = await api<{ commit: string }>("/api/delete", { items: ms.map((m) => ({ id: m.id, base: m.hash })) });
      for (const m of ms) this.picked.delete(m.id);
      if (this.openId && ms.some((m) => m.id === this.openId)) { this.openId = null; this.mode = "view"; this.writeRoute(); }
      await this.reload();
      this.toast(ms.length === 1 ? "Memory deleted" : `${ms.length} memories deleted`, { undo: r.commit });
    } catch (e) { this.toast((e as Error).message, { error: true }); }
  }
  togglePick(id: string) { if (this.picked.has(id)) this.picked.delete(id); else this.picked.add(id); }
  async undo(commit: string) {
    try { await api("/api/undo", { commit }); await this.reload(); this.toast("Undone"); }
    catch (e) { this.toast((e as Error).message, { error: true }); }
  }

  // ------------------------------------------------------------ keyboard cursor

  moveCursor(step: number) {
    if (!this.rows.length) return;
    this.cursor = Math.max(0, Math.min(this.rows.length - 1, (this.cursor < 0 ? (step > 0 ? -1 : this.rows.length) : this.cursor) + step));
    if (this.openId && this.mode === "view") this.openMemory(this.rows[this.cursor].id);  // reading along
  }
  openCursor() { const m = this.rows[this.cursor]; if (m) this.openMemory(m.id); }

  // ------------------------------------------------------------ toasts and confirmations

  private toastSeq = 0;
  toast(text: string, opts: { error?: boolean; undo?: string } = {}) {
    const t = { id: ++this.toastSeq, text, ...opts };
    this.toasts = [...this.toasts, t];
    setTimeout(() => this.dismiss(t.id), opts.undo ? 15000 : opts.error ? 8000 : 2500);
  }
  dismiss(id: number) { this.toasts = this.toasts.filter((t) => t.id !== id); }
  ask(q: Omit<Ask, "resolve">): Promise<boolean> {
    return new Promise((resolve) => { this.asking = { ...q, resolve }; });
  }
  answer(ok: boolean) { const a = this.asking; this.asking = null; a?.resolve(ok); }
}

export const app = new App();
