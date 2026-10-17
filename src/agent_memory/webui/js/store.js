// Everything the page knows and does, in one place: the memories, what the list shows, what is open,
// and the calls that change memories. Views read from `app`; anything that changes it calls app.changed(),
// which renders the page again once the current task is done (many changes, one render).
import { api, token } from "./api.js";
import { activeCount, listFilters, noFilters, passes, touched } from "./filters.js";
import { plural } from "./format.js";
import { lexical } from "./search.js";

const local = {
  get(k, d) {
    try { const v = localStorage.getItem("mem-ui-" + k); return v == null ? d : JSON.parse(v); } catch { return d; }
  },
  set(k, v) {
    try { localStorage.setItem("mem-ui-" + k, JSON.stringify(v)); } catch { /* private window */ }
  },
};
// saved choices are checked, since an older page on the same address may have stored other values
const pick = (value, allowed, fallback) => (allowed.includes(value) ? value : fallback);

const SORTERS = {
  new: (a, b) => (b.created || "").localeCompare(a.created || ""),
  old: (a, b) => (a.created || "").localeCompare(b.created || ""),
  edited: (a, b) => touched(b).localeCompare(touched(a)),
  az: (a, b) => a.description.localeCompare(b.description),
};

class App {
  data = null;
  bootError = "";
  page = "memories";
  openId = null;
  autoId = null;  // the memory a wide window shows before one is picked; it does not count as opened
  mode = "view";
  draft = null;
  formError = "";
  saving = false;
  tab = "memory";
  q = "";
  sem = [];
  semPending = false;
  filters = noFilters();
  menuQuery = "";
  sort = pick(local.get("sort", ""), ["new", "old", "edited", "az"], "new");
  theme = pick(local.get("theme", ""), ["system", "light", "dark"], "system");
  listWidth = local.get("list-width", null);
  picked = new Set();
  cursor = -1;
  toasts = [];
  asking = null;
  comparing = null;
  update = null;
  updating = "";
  insights = { commits: [], place: "", preview: null, hover: {} };
  settings = { s: null, checks: null, word: "", syncing: false, checking: false, lookingUp: false, failed: null,
    remoteEdit: false, remoteDraft: "", remoteBusy: false, remoteNote: null, healthOpen: false };
  profiles = null;  // { active, locked, demo, next, profiles }, from /api/profiles
  pform = null;  // the profile being added: its name to be, folder and remote
  switching = "";
  wide = matchMedia("(min-width: 1024px)");
  demo = null;  // the online demo sets { queries } to suggest searches
  #base = "";
  #listeners = [];
  #queued = false;

  onChange(fn) { this.#listeners.push(fn); }
  changed() {
    if (this.#queued) return;
    this.#queued = true;
    queueMicrotask(() => { this.#queued = false; this.#derive(); for (const fn of this.#listeners) fn(); });
  }

  // ------------------------------------------------------------ derived, worked out once per render

  M = [];
  byId = new Map();
  byName = new Map();
  termSets = new Map();
  kwName = new Map();
  places = [];
  filterDefs = [];
  groups = [];
  rows = [];
  #derive() {
    const M = (this.M = this.data?.memories ?? []);
    this.byId = new Map(M.map((m) => [m.id, m]));
    this.byName = new Map(M.map((m) => [String(m.meta?.name ?? ""), m]));
    this.termSets = new Map(M.map((m) => [m.id, new Set(m.terms)]));
    this.kwName = new Map(M.flatMap((m) => m.keywords.map((k) => [k.k, k.t])));
    this.places = this.data?.places ?? [];
    this.filterDefs = listFilters(M, this.places, this.filters, this.termSets, this.kwName);
    // the list: word matches (or every memory, sorted), then memories close in meaning that matched no word
    const ok = (m) => passes(m, this.filters, this.termSets.get(m.id));
    if (!this.q.trim()) this.groups = [{ title: null, items: M.filter(ok).sort(SORTERS[this.sort] ?? SORTERS.new) }];
    else {
      const lex = lexical(M, this.q).map((i) => M[i]).filter(ok);
      const seen = new Set(lex.map((m) => m.id));
      const sem = this.sem.map((h) => this.byId.get(h.id)).filter((m) => m && !seen.has(m.id) && ok(m)).slice(0, 8);
      this.groups = [{ title: null, items: lex }, ...(sem.length ? [{ title: "Close in meaning", items: sem }] : [])];
    }
    this.rows = this.groups.flatMap((g) => g.items);
    // on a wide window the reading pane is never empty: it shows the first memory until one is picked
    if (this.wide.matches && this.page === "memories" && !this.openId && this.mode === "view" && this.rows.length && !this.q.trim()) {
      this.autoId = this.openId = this.rows[0].id;
      this.tab = "memory";
      this.#writeRoute();
    }
  }
  get open() { return this.openId ? (this.byId.get(this.openId) ?? null) : null; }
  get filtering() { return activeCount(this.filters); }
  get unpushed() { return this.data?.sync?.remote ? (this.data.sync.ahead ?? 0) : 0; }
  /** Whether a memory or a form fills the window when it is too narrow for both panes. */
  get reading() { return (!!this.openId && this.openId !== this.autoId) || this.mode !== "view"; }
  get countText() {
    if (this.q.trim()) {
      const [words, meaning] = this.groups;
      return `${plural(words.items.length, "match", "matches")}${meaning ? ` · ${meaning.items.length} close in meaning` : ""}${this.semPending ? " · searching by meaning…" : ""}`;
    }
    return this.rows.length === this.M.length ? plural(this.M.length, "memory", "memories") : `${this.rows.length} of ${this.M.length}`;
  }

  // ------------------------------------------------------------ loading and routing

  async start() {
    if (!token) { this.bootError = "Open this page with the link that `mem ui` prints."; return this.changed(); }
    this.#readRoute();
    addEventListener("hashchange", () => { this.#readRoute(); this.changed(); });
    this.wide.addEventListener("change", () => this.changed());
    try { await this.reload(); }
    catch (e) {
      this.bootError = e.status === 401 ? "This link has expired. Run `mem ui` again and use the new link." : `Could not load memories: ${e.message}`;
      return this.changed();
    }
    this.refreshUpdate();  // checks PyPI at most once a day, unless turned off
    this.loadProfiles();
    // memories that agents write while the page is open
    setInterval(async () => {
      if (document.hidden || !this.data || this.mode !== "view") return;
      try { const st = await api("/api/stamp"); if (st.stamp !== this.data.stamp) await this.reload(); } catch { /* server stopped */ }
    }, 20000);
  }
  async reload() {
    this.data = await api("/api/state");
    const ids = new Set(this.data.memories.map((m) => m.id));
    for (const id of this.picked) if (!ids.has(id)) this.picked.delete(id);
    if (this.openId && !ids.has(this.openId) && this.mode !== "new") { this.openId = null; this.mode = "view"; this.#writeRoute(); }
    const keys = new Set((this.data.places ?? []).map((p) => "place:" + p.key));
    this.filters.loads = this.filters.loads.filter((v) => v === "global" || keys.has(v));
    if (this.page === "insights") this.loadActivity();
    this.changed();
  }
  #readRoute() {
    const [page, id] = location.hash.replace(/^#\/?/, "").split("/");
    this.page = page === "insights" || page === "settings" ? page : "memories";
    if (this.page === "memories" && id !== undefined) { this.openId = decodeURIComponent(id) || null; this.tab = "memory"; }
    this.#enterPage();
  }
  #writeRoute() {
    const hash = this.page === "memories" ? (this.openId ? `#/memories/${encodeURIComponent(this.openId)}` : "#/memories") : `#/${this.page}`;
    if (location.hash !== hash) history.replaceState(null, "", hash);
  }
  go(page) { this.page = page; this.#writeRoute(); this.#enterPage(); scrollTo(0, 0); this.changed(); }
  #enterPage() {
    if (this.page === "insights" && this.data) { this.loadActivity(); this.loadPreview(); }
    if (this.page === "settings") { this.loadSettings(); this.runChecks(); if (this.data) this.loadProfiles(); }
  }

  // ------------------------------------------------------------ updates

  async refreshUpdate(force = false) {
    try { this.update = force ? await api("/api/update/check", {}) : await api("/api/update"); this.changed(); }
    catch { /* offline: say nothing */ }
  }
  async setAutoUpdate(on) {
    await api("/api/settings", { check_updates: on });
    await this.refreshUpdate(on);
  }
  /** Update with uv, then restart mem ui on the new code and reload the page once it answers. */
  async runUpdate() {
    this.updating = "upgrading"; this.changed();
    let r;
    try { r = await api("/api/update", {}); }
    catch (e) { this.updating = ""; this.changed(); return { ok: false, error: e.message }; }
    if (!r.ok || !r.changed) {
      this.updating = ""; this.changed();
      if (r.ok) { this.toast("Already up to date"); await this.refreshUpdate(true); }
      return r;
    }
    this.updating = "restarting"; this.changed();
    try { await api("/api/restart", {}); } catch { /* the server may stop before it answers */ }
    const until = Date.now() + 60000;
    while (Date.now() < until) {
      await new Promise((ok) => setTimeout(ok, 800));
      try { await api("/api/stamp"); location.reload(); return r; } catch { /* not back yet */ }
    }
    this.updating = ""; this.changed();
    return { ...r, ok: false, error: `Updated to ${r.to}, but mem ui did not come back. Start it again in the terminal.` };
  }

  // ------------------------------------------------------------ preferences

  setTheme(v) { this.theme = v; local.set("theme", v); this.changed(); }
  setSort(v) { this.sort = v; local.set("sort", v); this.changed(); }
  setListWidth(v) { this.listWidth = v; local.set("list-width", v); this.changed(); }

  // ------------------------------------------------------------ search and filters

  #semTimer = 0;
  #semSeq = 0;
  search(text) {
    this.q = text;
    this.cursor = text.trim() ? 0 : -1;
    clearTimeout(this.#semTimer);
    this.changed();
    if (!text.trim()) { this.sem = []; this.semPending = false; return; }
    this.semPending = !!this.data?.semantic;
    if (!this.semPending) return;
    const seq = ++this.#semSeq, query = text.trim();
    this.#semTimer = setTimeout(async () => {
      try {
        const r = await api(`/api/search?q=${encodeURIComponent(query)}`);
        if (seq === this.#semSeq) this.sem = r.hits || [];
      } catch { /* word matches stay */ }
      if (seq === this.#semSeq) { this.semPending = false; this.changed(); }
    }, 300);
  }
  setList(key, values) { this.filters[key] = values; this.cursor = -1; this.changed(); }
  toggle(key, v) { const cur = this.filters[key]; this.setList(key, cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v]); }
  setAdded(v) { this.filters.added = v; this.cursor = -1; this.changed(); }
  clearFilters() { this.filters = noFilters(); this.cursor = -1; this.changed(); }

  // ------------------------------------------------------------ open, edit, new

  #dirty() { return !!this.draft && JSON.stringify(this.draft) !== this.#base; }
  async #leaveEdit() {
    if (this.mode === "view" || !this.#dirty()) return true;
    return this.ask({ title: "Discard your changes?", body: "What you typed in the form will be lost.", action: "Discard", danger: true });
  }
  async openMemory(id) {
    if (!(await this.#leaveEdit())) return;
    if (this.page !== "memories") { this.page = "memories"; scrollTo(0, 0); }
    this.mode = "view"; this.draft = null; this.formError = "";
    if (this.openId !== id) this.tab = "memory";
    this.openId = id; this.autoId = null;
    const k = this.rows.findIndex((m) => m.id === id);
    if (k >= 0) this.cursor = k;
    this.#writeRoute();
    this.changed();
  }
  async openByName(name) { const m = this.byName.get(name); if (m) await this.openMemory(m.id); }
  async close() {
    if (!(await this.#leaveEdit())) return;
    this.mode = "view"; this.draft = null; this.openId = null; this.autoId = null;
    this.#writeRoute();
    this.changed();
  }
  async startNew() {
    if (!(await this.#leaveEdit())) return;
    if (this.page !== "memories") this.go("memories");
    this.openId = null; this.autoId = null; this.mode = "new"; this.formError = "";
    this.draft = { description: "", type: "feedback", scope: "global", place: "", pathMode: false, path: "", body: "" };
    this.#base = JSON.stringify(this.draft);
    this.changed();
  }
  startEdit() {
    const m = this.open;
    if (!m) return;
    this.mode = "edit"; this.formError = "";
    this.draft = { description: m.description, type: m.type, scope: m.scope, place: m.scope === "here" ? m.place : "", pathMode: false, path: "", body: m.body };
    this.#base = JSON.stringify(this.draft);
    this.changed();
  }
  async cancelEdit() {
    if (!(await this.#leaveEdit())) return;
    this.mode = "view"; this.draft = null; this.formError = "";
    if (!this.openId) this.#writeRoute();
    this.changed();
  }
  setDraft(field, value) { if (this.draft) { this.draft[field] = value; this.changed(); } }
  /** Saves the form; a problem shows in the form. */
  async save() {
    const d = this.draft;
    if (!d || this.saving) return;
    this.formError = await this.#save(d);
    this.saving = false;
    this.changed();
  }
  async #save(d) {
    if (!d.description.trim()) return "Add a one-line description.";
    let place = null;
    if (d.scope === "here") {
      if (d.pathMode) { if (!d.path.trim()) return "Type the folder path."; place = { path: d.path.trim() }; }
      else if (d.place) place = { key: d.place };
      else return "Choose where it loads.";
    }
    this.saving = true; this.changed();
    try {
      if (this.mode === "new") {
        const r = await api("/api/create", { type: d.type, scope: d.scope, description: d.description, body: d.body, place });
        this.mode = "view"; this.draft = null;
        await this.reload();
        await this.openMemory(r.id);
        this.toast("Memory added", { undo: r.commit });
      } else {
        const m = this.open;
        const change = {};
        if (d.description !== m.description) change.description = d.description;
        if (d.type !== m.type) change.type = d.type;
        if (d.scope !== m.scope) change.scope = d.scope;
        if (d.body !== m.body) change.body = d.body;
        if (place && (place.path || place.key !== m.place)) change.place = place;
        const r = await api("/api/edit", { id: m.id, base: m.hash, change });
        this.mode = "view"; this.draft = null;
        await this.reload();
        if (r.commit) this.toast("Saved", { undo: r.commit });
      }
      return "";
    } catch (e) { return e.message; }
  }

  // ------------------------------------------------------------ delete, select, undo

  async remove(ids) {
    const ms = ids.map((id) => this.byId.get(id)).filter(Boolean);
    if (!ms.length) return;
    const ok = await this.ask(ms.length === 1
      ? { title: "Delete this memory?", body: ms[0].description, action: "Delete", danger: true }
      : { title: `Delete ${ms.length} memories?`, body: ms.slice(0, 5).map((m) => `• ${m.description}`).join("\n") + (ms.length > 5 ? `\n…and ${ms.length - 5} more` : ""), action: `Delete ${ms.length}`, danger: true });
    if (!ok) return;
    try {
      const r = await api("/api/delete", { items: ms.map((m) => ({ id: m.id, base: m.hash })) });
      for (const m of ms) this.picked.delete(m.id);
      if (this.openId && ms.some((m) => m.id === this.openId)) { this.openId = null; this.autoId = null; this.mode = "view"; this.#writeRoute(); }
      await this.reload();
      this.toast(ms.length === 1 ? "Memory deleted" : `${ms.length} memories deleted`, { undo: r.commit });
    } catch (e) { this.toast(e.message, { error: true }); }
  }
  togglePick(id) { if (this.picked.has(id)) this.picked.delete(id); else this.picked.add(id); this.changed(); }
  pickAll(ids) { for (const id of ids) this.picked.add(id); this.changed(); }
  clearPicked() { this.picked.clear(); this.changed(); }
  async undo(commit) {
    try { await api("/api/undo", { commit }); await this.reload(); this.toast("Undone"); }
    catch (e) { this.toast(e.message, { error: true }); }
  }

  // ------------------------------------------------------------ keyboard cursor

  moveCursor(step) {
    if (!this.rows.length) return;
    this.cursor = Math.max(0, Math.min(this.rows.length - 1, (this.cursor < 0 ? (step > 0 ? -1 : this.rows.length) : this.cursor) + step));
    if (this.openId && this.mode === "view") this.openMemory(this.rows[this.cursor].id);  // reading along
    else this.changed();
  }
  openCursor() { const m = this.rows[this.cursor]; if (m) this.openMemory(m.id); }

  // ------------------------------------------------------------ insights and settings

  async loadActivity() {
    try { this.insights.commits = (await api("/api/activity")).commits; this.changed(); } catch { /* the chart stays empty */ }
  }
  async loadPreview(place = this.insights.place) {
    this.insights.place = place;
    try {
      const r = await api(`/api/index-preview?place=${encodeURIComponent(place)}`);
      if (place === this.insights.place) this.insights.preview = r;
    } catch { this.insights.preview = null; }
    this.changed();
  }
  async loadSettings() {
    try { this.settings.s = await api("/api/settings"); this.changed(); } catch (e) { this.toast(e.message, { error: true }); }
  }
  async runChecks() {
    this.settings.checking = true; this.changed();
    try { this.settings.checks = (await api("/api/doctor")).checks; } catch { /* keep the last result */ }
    this.settings.checking = false; this.changed();
  }

  // ------------------------------------------------------------ profiles

  async loadProfiles() {
    try { this.profiles = await api("/api/profiles"); this.changed(); } catch { /* an older server: no profiles */ }
  }
  /** Show another profile, which new sessions then use too. */
  async useProfile(id) {
    if (this.switching) return;
    if (this.profiles?.active === id) return this.pform && this.cancelProfile();
    if (!(await this.#leaveEdit())) return;
    const to = this.profiles?.profiles.find((p) => p.id === id);
    this.switching = id; this.changed();
    try {
      this.#took(await api("/api/profiles/use", { id }));
      this.toast(`Switched to ${to?.name ?? id}${this.profiles?.demo ? "" : "; new sessions use it too"}`);
    } catch (e) { this.toast(e.message, { error: true }); }
    finally { this.switching = ""; this.changed(); }
  }
  /** After the server answers a profile change: its list, and the memories of the profile it now shows. */
  async #took(r) {
    const before = this.profiles?.active;
    this.profiles = r; this.pform = null;
    if (r.active === before) return this.changed();
    this.openId = this.autoId = null; this.mode = "view"; this.draft = null; this.picked.clear();
    this.q = ""; this.sem = []; this.filters = noFilters(); this.cursor = -1;
    this.data = { ...this.data, memories: [], places: [] };  // so nothing of the old profile is picked meanwhile
    Object.assign(this.insights, { commits: [], place: "", preview: null, hover: {} });
    Object.assign(this.settings, { s: null, checks: null, remoteEdit: false, remoteNote: null, healthOpen: false });
    this.#writeRoute();
    await this.reload();
    this.#enterPage();
  }
  /** Start adding a profile; its name is the one the server will give it, its folder goes beside the active one. */
  async newProfile() {
    await this.loadProfiles();  // a fresh name to show
    const name = this.profiles?.next ?? "";
    const here = this.profiles?.profiles.find((p) => p.active)?.dataDir ?? "";
    const near = here.includes("/") ? here.slice(0, here.lastIndexOf("/") + 1) : "~/";
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    this.pform = { name, folder: `${near}agent-memory-${slug}`, remote: "", busy: false, error: "" };
    this.changed();
  }
  setProfileField(field, value) {
    if (!this.pform) return;
    this.pform[field] = value; this.pform.error = "";
    this.changed();
  }
  async saveProfile() {
    const f = this.pform;
    if (!f || f.busy) return;
    f.busy = true; f.error = ""; this.changed();
    try {
      const r = await api("/api/profiles/add", { name: f.name, folder: f.folder, remote: f.remote.trim() || null });
      const made = r.profiles.find((p) => p.id === r.id)?.name ?? f.name;
      await this.#took(r);
      this.toast(r.demo || r.active !== r.id ? `${made}: ${r.message}` : `${made}: ${r.message} New sessions use it.`);
    } catch (e) { f.busy = false; f.error = e.message; this.changed(); }
  }
  /** Forget the profile the page shows, after asking; its folder and remote stay. */
  async removeProfile() {
    const p = this.profiles?.profiles.find((x) => x.active);
    if (!p) return;
    const ok = await this.ask({ title: `Remove the ${p.name} profile?`, body: `agent-memory stops using it. The folder ${p.dataDir} and its memories stay on disk, and any remote is not touched; add the folder again later to bring it back.`, action: "Remove", danger: true });
    if (!ok) return;
    try { await this.#took(await api("/api/profiles/remove", { id: p.id })); this.toast(`Removed ${p.name}`); }
    catch (e) { this.toast(e.message, { error: true }); }
  }
  cancelProfile() { this.pform = null; this.changed(); }

  // ------------------------------------------------------------ toasts and confirmations

  #toastSeq = 0;
  toast(text, opts = {}) {
    const t = { id: ++this.#toastSeq, text, ...opts };
    this.toasts = [...this.toasts, t];
    setTimeout(() => this.dismiss(t.id), opts.undo ? 15000 : opts.error ? 8000 : 2500);
    this.changed();
  }
  dismiss(id) { this.toasts = this.toasts.filter((t) => t.id !== id); this.changed(); }
  ask(q) { return new Promise((resolve) => { this.asking = { ...q, resolve }; this.changed(); }); }
  answer(ok) { const a = this.asking; this.asking = null; a?.resolve(ok); this.changed(); }
}

export const app = new App();
