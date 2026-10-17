// Starts the page: renders the views whenever the store changes, and turns clicks, typing and keys into
// store calls. Elements say what they do with data-act (click), data-input (typing) and data-change.
import { api } from "./api.js";
import { morph } from "./h.js";
import { app } from "./store.js";
import { duplicatePairs } from "./views/insights.js";
import { OTHER } from "./views/memory.js";
import { compareDialog, confirmDialog } from "./views/overlays.js";
import { view } from "./views/shell.js";

const root = document.getElementById("app");
const confirmEl = document.getElementById("confirm");
const compareEl = document.getElementById("compare");

// ---------------------------------------------------------------- rendering

let lastCursor = -1, lastMode = "view";
function render() {
  const el = document.documentElement;
  if (app.theme === "system") delete el.dataset.theme;
  else el.dataset.theme = app.theme;
  const words = { memories: "Memories", insights: "Insights", settings: "Settings" };
  document.title = `${app.open && app.page === "memories" ? app.open.description : words[app.page]} · agent-memory`;

  morph(root, view());
  modal(confirmEl, confirmDialog(), !!app.asking);
  modal(compareEl, compareDialog(), !!app.comparing);

  if (app.cursor !== lastCursor) root.querySelector(`[data-k="${app.cursor}"]`)?.scrollIntoView({ block: "nearest" });
  if (app.mode === "new" && lastMode !== "new") document.getElementById("f-desc")?.focus();
  lastCursor = app.cursor; lastMode = app.mode;
  for (const box of root.querySelectorAll("[data-chart]")) sizes.observe(box);
}
function modal(dialog, content, open) {
  if (content) morph(dialog, content);
  if (open && !dialog.open) { dialog.showModal(); dialog.querySelector("[autofocus]")?.focus(); }
  else if (!open && dialog.open) dialog.close();
}
confirmEl.addEventListener("close", () => { if (app.asking) app.answer(false); });
compareEl.addEventListener("close", () => { if (app.comparing) { app.comparing = null; app.changed(); } });
for (const d of [confirmEl, compareEl]) d.addEventListener("click", (e) => { if (e.target === d) d.close(); });  // the backdrop

// charts are drawn as wide as their box
const sizes = new ResizeObserver((entries) => {
  const width = (app.insights.width ??= {});
  for (const e of entries) {
    const id = e.target.dataset.chart, w = Math.round(e.contentRect.width);
    if (w && width[id] !== w) { width[id] = w; app.changed(); }
  }
});

// ---------------------------------------------------------------- what elements do

const copy = async (text, said = "Copied") => {
  try { await navigator.clipboard.writeText(text); app.toast(said); } catch { prompt("Copy:", text); }
};
const closeMenus = () => document.querySelectorAll(".menu:popover-open").forEach((m) => m.hidePopover());
const settings = app.settings;

async function saveWords(words) {
  try { settings.s = await api("/api/settings", { keyword_stopwords: words }); await app.reload(); app.toast("Keywords updated"); }
  catch (e) { app.toast(e.message, { error: true }); }
}
async function setRemote(url) {
  if (url !== null && !url) return;
  Object.assign(settings, { remoteBusy: true, remoteNote: null }); app.changed();
  try {
    const r = await api("/api/remote", { url });
    settings.s = r.settings;
    Object.assign(settings, { remoteEdit: !r.ok && url !== null, remoteNote: { ok: r.ok, text: r.message } });
    await app.reload();
  } catch (e) { settings.remoteNote = { ok: false, text: e.message }; }
  finally { settings.remoteBusy = false; app.changed(); }
}
function filterAndGo(key, value) { app.clearFilters(); app.setList(key, [value]); app.go("memories"); }
const pair = (arg) => { const i = arg.indexOf(":"); return [arg.slice(0, i), arg.slice(i + 1)]; };

const ACTIONS = {
  go: (page) => app.go(page),
  home: () => (app.page === "memories" ? app.close() : app.go("memories")),
  close: () => app.close(),
  startNew: () => app.startNew(),
  startEdit: () => app.startEdit(),
  cancelEdit: () => app.cancelEdit(),
  removeOpen: () => app.open && app.remove([app.open.id]),
  copyPath: () => app.open && copy(app.open.path, "Path copied"),
  copy: (text) => copy(text),
  open: (id) => { if (app.comparing) { app.comparing = null; } app.openMemory(id); },
  openName: (name, el, e) => { e.preventDefault(); app.openByName(name); },
  row: (id, el, e) => (e.metaKey || e.shiftKey || e.ctrlKey ? app.togglePick(id) : app.openMemory(id)),
  pick: (id, el, e) => { e.stopPropagation(); app.togglePick(id); },
  tab: (v) => { app.tab = v; app.changed(); },
  toggle: (arg) => app.toggle(...pair(arg)),
  setList: (key) => app.setList(key, []),
  setAdded: (v) => app.setAdded(v),
  clearFilters: () => app.clearFilters(),
  setSort: (v) => { app.setSort(v); closeMenus(); },
  clearSearch: () => { app.search(""); document.getElementById("q")?.focus(); },
  trySearch: (q) => app.search(q),
  pickAll: () => app.pickAll(app.rows.map((m) => m.id)),
  clearPicked: () => app.clearPicked(),
  removePicked: () => app.remove([...app.picked]),
  undoToast: (id) => { const t = app.toasts.find((x) => String(x.id) === id); if (t) { app.dismiss(t.id); app.undo(t.undo); } },
  answer: (v) => app.answer(v === "yes"),
  compare: (i) => { app.comparing = duplicatePairs()[Number(i)] ?? null; app.changed(); },
  closeCompare: () => { app.comparing = null; app.changed(); },
  removeCompared: (id) => { app.comparing = null; app.remove([id]); },
  showStatus: (f) => filterAndGo("status", f),
  showLoads: (key) => filterAndGo("loads", key),
  showTool: (key) => filterAndGo("tool", key),
  chartTable: (id) => { const t = (app.insights.table ??= {}); t[id] = !t[id]; app.changed(); },
  draftType: (v) => app.setDraft("type", v),
  draftScope: (v) => app.setDraft("scope", v),
  setTheme: (v) => app.setTheme(v),
  runUpdate: async () => { settings.failed = null; const r = await app.runUpdate(); if (!r.ok) { settings.failed = r; app.changed(); } },
  checkNow: async () => { settings.lookingUp = true; settings.failed = null; app.changed(); try { await app.refreshUpdate(true); } finally { settings.lookingUp = false; app.changed(); } },
  autoUpdate: () => app.setAutoUpdate(!(app.update?.auto ?? true)),
  syncNow: async () => {
    settings.syncing = true; app.changed();
    try {
      const r = await api("/api/sync", {});
      await app.reload(); await app.loadSettings();
      app.toast(r.ok ? "Synced" : "Sync failed; see .cache/agent-memory.log in the data repository", { error: !r.ok });
    } catch (e) { app.toast(e.message, { error: true }); }
    finally { settings.syncing = false; app.changed(); }
  },
  removeWord: (w) => settings.s && saveWords(settings.s.keywordStopwords.filter((x) => x !== w)),
  remoteEdit: () => {
    Object.assign(settings, { remoteEdit: true, remoteDraft: settings.s?.remoteUrl ?? "", remoteNote: null }); app.changed();
    setTimeout(() => document.getElementById("remote-url")?.focus());  // once the form is drawn
  },
  remoteCancel: () => { Object.assign(settings, { remoteEdit: false, remoteNote: null }); app.changed(); },
  remoteSave: () => setRemote(settings.remoteDraft.trim()),
  remoteDisconnect: async () => {
    const ok = await app.ask({ title: "Disconnect the remote?", body: "Memories stay in this repository and keep being committed; they are just no longer pushed or pulled. The remote itself is not touched.", action: "Disconnect", danger: true });
    if (ok) setRemote(null);
  },
  toggleHealth: () => { settings.healthOpen = !settings.healthOpen; app.changed(); },
  runChecks: () => app.runChecks(),
};

const INPUTS = {
  search: (v) => app.search(v),
  menuQuery: (v) => { app.menuQuery = v; app.changed(); },
  word: (v) => { settings.word = v; },
  remoteDraft: (v) => { settings.remoteDraft = v; app.changed(); },
};
const CHANGES = {
  rangeFrom: (v) => { const r = rangeOf(); app.setAdded(v || r[1] ? `range:${v}:${r[1]}` : ""); },
  rangeTo: (v) => { const r = rangeOf(); app.setAdded(r[0] || v ? `range:${r[0]}:${v}` : ""); },
  draftPlace: (v) => { if (!app.draft) return; app.draft.pathMode = v === OTHER; app.draft.place = v === OTHER ? "" : v; app.changed(); },
  previewPlace: (v) => app.loadPreview(v),
};
const rangeOf = () => (app.filters.added.startsWith("range:") ? app.filters.added.split(":").slice(1) : ["", ""]);

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (!el || el.disabled) return;
  ACTIONS[el.dataset.act]?.(el.dataset.arg ?? "", el, e);
});
document.addEventListener("input", (e) => {
  const el = e.target, name = el.dataset?.input;
  if (!name) return;
  if (name.startsWith("draft:")) app.setDraft(name.slice(6), el.value);
  else INPUTS[name]?.(el.value);
});
document.addEventListener("change", (e) => { const name = e.target.dataset?.change; if (name) CHANGES[name]?.(e.target.value); });
document.addEventListener("submit", (e) => { if (e.target.matches("[data-memory-form]")) { e.preventDefault(); app.save(); } });

// ---------------------------------------------------------------- menus

// a menu opens under the button that names it, kept inside the window
document.addEventListener("beforetoggle", (e) => {
  const menu = e.target;
  if (!menu.classList?.contains("menu") || e.newState !== "open") return;
  const trigger = document.querySelector(`[popovertarget="${menu.id}"]`);
  if (!trigger) return;
  const r = trigger.getBoundingClientRect(), w = parseFloat(getComputedStyle(menu).width) || 288;
  const left = menu.dataset.align === "end" ? r.right - w : r.left;
  menu.style.left = `${Math.max(8, Math.min(innerWidth - w - 8, left))}px`;
  menu.style.top = `${r.bottom + 4}px`;
  menu.style.maxHeight = `${Math.max(160, innerHeight - r.bottom - 16)}px`;
  if (menu.querySelector(".menu-find")) { app.menuQuery = ""; app.changed(); }
}, true);
document.addEventListener("toggle", (e) => {
  const menu = e.target;
  if (!menu.classList?.contains("menu") || e.newState !== "open") return;
  (menu.querySelector(".menu-find") || menu.querySelector('.menu-item[aria-checked="true"]') || menu.querySelector(".menu-item"))?.focus();
}, true);
addEventListener("resize", closeMenus);

function menuKeys(e, menu) {
  const items = [...menu.querySelectorAll(".menu-item")];
  const at = items.indexOf(document.activeElement);
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    const next = at < 0 ? (e.key === "ArrowDown" ? 0 : items.length - 1) : (at + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
    items[next]?.focus();
  } else if (e.key === "Enter" && document.activeElement?.classList.contains("menu-find")) {
    e.preventDefault();
    items[0]?.click();
  }
}

// ---------------------------------------------------------------- the line between the list and the memory

const MIN = 280, READ_MIN = 420, STEP = 16;
let dragging = null;
const paneOf = (handle) => handle.closest(".list-pane");
const maxWidth = (pane) => Math.max(MIN, Math.min(720, (pane.parentElement?.clientWidth ?? 1200) - READ_MIN));
const setWidth = (pane, w) => app.setListWidth(Math.round(Math.min(maxWidth(pane), Math.max(MIN, w))));
document.addEventListener("pointerdown", (e) => {
  const handle = e.target.closest("[data-resize]");
  if (!handle || e.button !== 0) return;
  e.preventDefault();
  try { handle.setPointerCapture(e.pointerId); } catch { /* a pointer the browser no longer tracks */ }
  dragging = paneOf(handle);
  document.body.classList.add("resizing");
});
document.addEventListener("pointermove", (e) => { if (dragging) setWidth(dragging, e.clientX - dragging.getBoundingClientRect().left); });
const stop = () => { dragging = null; document.body.classList.remove("resizing"); };
document.addEventListener("pointerup", stop);
document.addEventListener("pointercancel", stop);
document.addEventListener("dblclick", (e) => { if (e.target.closest("[data-resize]")) app.setListWidth(null); });

function resizeKeys(e, handle) {
  const pane = paneOf(handle), now = pane.getBoundingClientRect().width;
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") setWidth(pane, now + (e.key === "ArrowRight" ? STEP : -STEP));
  else if (e.key === "Home") setWidth(pane, MIN);
  else if (e.key === "End") setWidth(pane, maxWidth(pane));
  else return;
  e.preventDefault(); e.stopPropagation();
}

// ---------------------------------------------------------------- chart hover

document.addEventListener("pointerover", (e) => {
  const week = e.target.closest?.("[data-week]"), box = week?.closest("[data-chart]");
  if (!box) return;
  const id = box.dataset.chart, i = Number(week.dataset.week);
  if (app.insights.hover[id] !== i) { app.insights.hover[id] = i; app.changed(); }
});
document.addEventListener("pointerout", (e) => {
  const box = e.target.closest?.("[data-chart]");
  if (box && !box.contains(e.relatedTarget)) { app.insights.hover[box.dataset.chart] = null; app.changed(); }
});

// ---------------------------------------------------------------- keys

addEventListener("keydown", (e) => {
  const el = document.activeElement;
  const menu = el?.closest?.(".menu");
  if (menu) return menuKeys(e, menu);
  if (el?.matches?.("[data-resize]")) return resizeKeys(e, el);
  if (el?.id === "q") {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); return app.moveCursor(e.key === "ArrowDown" ? 1 : -1); }
    if (e.key === "Enter") { e.preventDefault(); return app.openCursor(); }
    if (e.key === "Escape") { e.stopPropagation(); return app.q ? app.search("") : el.blur(); }
  }
  if (el?.id === "remote-url" && (e.key === "Enter" || e.key === "Escape")) {
    e.preventDefault();
    return e.key === "Enter" ? setRemote(settings.remoteDraft.trim()) : ACTIONS.remoteCancel();
  }
  if (el?.id === "add-word" && e.key === "Enter") {
    e.preventDefault();
    const w = settings.word.trim().toLowerCase(), s = settings.s;
    settings.word = ""; el.value = "";
    if (w && s && !s.keywordStopwords.includes(w)) saveWords([...s.keywordStopwords, w]);
    return;
  }
  if (app.asking || app.comparing || document.querySelector(".menu:popover-open")) return;  // a dialog or menu handles its own keys
  const typing = !!el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s" && app.mode !== "view") {
    e.preventDefault();
    return app.save();
  }
  if (e.key === "Escape") {
    if (typing) return el.blur();
    if (app.mode !== "view") return app.cancelEdit();
    if (app.openId && !app.wide.matches && app.reading) return app.close();  // narrow: back to the list
    if (app.picked.size) return app.clearPicked();
    if (app.q) return app.search("");
    return;
  }
  if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key;
  if (k === "/") { e.preventDefault(); if (app.page !== "memories") app.go("memories"); requestAnimationFrame(() => document.getElementById("q")?.focus()); }
  else if (k === "n") { e.preventDefault(); app.startNew(); }
  else if (app.page !== "memories" || app.mode !== "view") return;
  else if (k === "e" && app.open) { e.preventDefault(); app.startEdit(); }
  else if (k === "j" || k === "ArrowDown") { e.preventDefault(); app.moveCursor(1); }
  else if (k === "k" || k === "ArrowUp") { e.preventDefault(); app.moveCursor(-1); }
  else if (k === "Enter") { e.preventDefault(); app.openCursor(); }
  else if (k === "x" && app.rows[app.cursor]) { e.preventDefault(); app.togglePick(app.rows[app.cursor].id); }
});

app.onChange(render);
app.changed();
app.start();
