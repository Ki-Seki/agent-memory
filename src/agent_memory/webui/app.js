(() => {
  "use strict";

  // ------------------------------------------------------------ plumbing
  const token = (location.hash.match(/t=([\w-]+)/) || [])[1] || sessionStorage.getItem("mem-ui-token") || "";
  if (token) sessionStorage.setItem("mem-ui-token", token);
  if (location.hash) history.replaceState(null, "", location.pathname);  // keep the token out of sight
  addEventListener("hashchange", () => location.reload());  // a new link from `mem ui`

  async function api(path, body) {
    const r = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: { "X-Mem-Token": token, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(data.error || `${r.status} ${r.statusText}`), { status: r.status });
    return data;
  }
  const $ = id => document.getElementById(id);
  function el(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k === "value") n.value = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    return n;
  }
  const ICON = {
    edit: '<path d="M11 2.5l2.5 2.5L6 12.5H3.5V10z"/>',
    trash: '<path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8.5h5.8l.6-8.5"/>',
    close: '<path d="M4 4l8 8M12 4l-8 8"/>',
    copy: '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M3 10.5V3.5a1 1 0 0 1 1-1h6.5"/>',
  };
  function iconBtn(name, label, onclick) {
    const b = el("button", { class: "icon-btn", title: label, "aria-label": label, onclick });
    b.innerHTML = `<svg viewBox="0 0 16 16" aria-hidden="true">${ICON[name]}</svg>`;  // static markup only
    return b;
  }
  const day = iso => {
    const t = Date.parse(iso || "");
    return t ? new Date(t).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "";
  };
  const plural = (n, one, many) => `${n} ${n === 1 ? one : (many || one + "s")}`;
  const local = {
    get(k, d) { try { const v = localStorage.getItem("mem-ui-" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("mem-ui-" + k, JSON.stringify(v)); } catch (e) { /* private window */ } },
  };
  function toast(message, opts = {}) {
    const t = el("div", { class: "toast" + (opts.error ? " error" : "") }, el("span", { text: message }));
    if (opts.undo) t.append(el("button", { text: "Undo", onclick: async () => {
      t.remove();
      try { await api("/api/undo", { commit: opts.undo }); await reload(); toast("Undone"); }
      catch (e) { toast(e.message, { error: true }); }
    } }));
    $("toasts").append(t);
    setTimeout(() => t.remove(), opts.undo ? 15000 : opts.error ? 8000 : 2500);
  }

  // ------------------------------------------------------------ data
  let D = null, M = [], byId = new Map(), byName = new Map(), kwName = new Map();
  const S = {
    open: null, mode: "view", tab: "rendered",
    q: "", lex: [], sem: [],
    f: { type: [], loads: [], tool: [], kw: [], added: "", status: [] }, sort: local.get("sort", "new"), countText: "", menu: null, menuFind: "",
    picked: new Set(), rows: [], cursor: -1,
  };

  async function reload() {
    const d = await api("/api/state");
    D = d; M = d.memories;
    byId = new Map(M.map((m, i) => [m.id, i]));
    byName = new Map(M.map((m, i) => [m.meta && m.meta.name, i]));
    M.forEach(m => { m.termSet = new Set(m.terms || []); m.day = localDay(m.created); });
    kwName = new Map();
    M.forEach(m => (m.keywords || []).forEach(k => kwName.set(k.k, k.t)));
    S.picked.forEach(id => { if (!byId.has(id)) S.picked.delete(id); });
    if (S.open && !byId.has(S.open)) closeDrawer(true);
    S.f.loads = S.f.loads.filter(v => v === "global" || (D.places || []).some(p => "place:" + p.key === v));
    renderStatus();
    if (S.q) runSearch(S.q, false);
    renderFilters();
    renderList();
    if (S.open && S.mode === "view") renderDrawer();
  }

  // ------------------------------------------------------------ filters
  const TYPES = ["user", "feedback", "project", "reference"];
  const SORTS = [["new", "Newest first"], ["old", "Oldest first"], ["edited", "Recently changed"], ["az", "A to Z"]];
  const ADDED = [["today", "Today"], ["7", "Past 7 days"], ["30", "Past 30 days"], ["90", "Past 3 months"], ["365", "Past year"]];
  const STATUS = [["tidy", "needs tidying"], ["stale", "unchanged 60+ days"]];
  const DAY = 864e5;
  const touched = m => m.updated || m.created || "";
  const ymd = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const localDay = iso => { const t = Date.parse(iso || ""); return t ? ymd(new Date(t)) : ""; };
  const shortDay = s => new Date(`${s}T00:00`).toLocaleDateString(undefined,
    { month: "short", day: "numeric", year: s.slice(0, 4) === String(new Date().getFullYear()) ? undefined : "numeric" });

  // Added holds one choice: a preset ("today", or the number of days back) or "range:<from>:<to>" with either end open
  function addedOk(m, added) {
    if (!added) return true;
    if (!m.day) return false;
    if (added === "today") return m.day === ymd(new Date());
    if (added.startsWith("range:")) { const [, from, to] = added.split(":"); return (!from || m.day >= from) && (!to || m.day <= to); }
    return Date.now() - Date.parse(m.created) <= Number(added) * DAY;
  }
  // the other filters hold any number of values; a memory needs to match one of them
  const TEST = {
    type: (m, v) => m.type === v,
    loads: (m, v) => v === "global" ? m.scope === "global" : m.scope === "here" && m.place === v.slice(6),
    tool: (m, v) => m.tool === v,
    kw: (m, v) => m.termSet.has(v),
    status: (m, v) => v === "tidy" ? (m.issues || []).length > 0 : Date.now() - (Date.parse(touched(m)) || Date.now()) >= 60 * DAY,
  };
  const noFilters = () => ({ type: [], loads: [], tool: [], kw: [], added: "", status: [] });
  const filtering = () => Object.values(S.f).filter(v => v.length).length;
  // skip leaves one filter out, so its menu can count what each of its options would show
  function passes(m, skip) {
    for (const [key, test] of Object.entries(TEST)) if (key !== skip && S.f[key].length && !S.f[key].some(v => test(m, v))) return false;
    return skip === "added" || addedOk(m, S.f.added);
  }
  // keywords that tag at least two memories, most common first; chosen ones always listed
  function keywordOptions() {
    const n = new Map();
    M.forEach(m => { if (passes(m, "kw")) m.termSet.forEach(t => { if (kwName.has(t)) n.set(t, (n.get(t) || 0) + 1); }); });
    const out = [...n].filter(([, c]) => c >= 2).sort((a, b) => b[1] - a[1] || kwName.get(a[0]).localeCompare(kwName.get(b[0]))).slice(0, 80);
    for (const k of S.f.kw) if (!out.some(([x]) => x === k)) out.unshift([k, n.get(k) || 0]);
    return out.map(([k, c]) => [k, kwName.get(k) || k, c]);
  }
  // every filter as data, options as [value, label, count]
  function filterDefs() {
    const opts = (key, list) => list.map(([v, t]) => [v, t, M.filter(m => passes(m, key) && TEST[key](m, v)).length]);
    const tools = [...new Set(M.map(m => m.tool).filter(Boolean))].sort();
    return [
      { key: "type", label: "Type", any: "All", options: opts("type", TYPES.map(t => [t, t])) },
      { key: "loads", label: "Loads in", any: "Anywhere", options: opts("loads", [["global", "everywhere"], ...(D.places || []).map(p => ["place:" + p.key, p.key])]) },
      tools.length > 1 ? { key: "tool", label: "Source", any: "Any", options: opts("tool", tools.map(t => [t, t])) } : null,
      { key: "kw", label: "Keyword", any: "Any", options: keywordOptions(), find: true },
      { key: "added", label: "Added", any: "Any time", single: true, options: ADDED.map(([v, t]) => [v, t, M.filter(m => passes(m, "added") && addedOk(m, v)).length]) },
      { key: "status", label: "Status", any: "Any", options: opts("status", STATUS) },
    ].filter(Boolean);
  }
  // the button keeps short: a place shows as its last folder (the menu and the tooltip show it whole)
  function shownAs(d, whole) {
    const v = S.f[d.key], full = x => (d.options.find(([o]) => o === x) || [x, x])[1];
    const name = x => !whole && x.startsWith("place:") ? x.split("/").filter(Boolean).pop() : full(x);
    if (!v.length) return d.any;
    if (d.single) {
      if (!v.startsWith("range:")) return name(v);
      const [, from, to] = v.split(":");
      return from && to ? `${shortDay(from)} – ${shortDay(to)}` : from ? `since ${shortDay(from)}` : `until ${shortDay(to)}`;
    }
    return whole ? v.map(full).join(", ") : v.length === 1 ? name(v[0]) : `${name(v[0])} +${v.length - 1}`;
  }
  function setFilter(key, v) {
    S.f[key] = v; S.cursor = -1;
    renderFilters(); renderList(); scrollTo(0, 0);
    if (key === "kw" && S.open && S.mode === "view") renderDrawer();
  }
  const toggleValue = (key, v) => setFilter(key, S.f[key].includes(v) ? S.f[key].filter(x => x !== v) : [...S.f[key], v]);
  function clearFilters() { S.f = noFilters(); S.menu = null; S.cursor = -1; renderFilters(); renderList(); }
  const setKeyword = k => toggleValue("kw", k);
  function keywordChips(m) {
    if (!(m.keywords || []).length) return null;
    return el("div", { class: "kws" }, m.keywords.map(k => {
      const on = S.f.kw.includes(k.k);
      return el("button", { class: "kw" + (on ? " on" : ""), text: k.t, title: on ? `Stop filtering by ${k.t}` : `Only memories that mention ${k.t}`,
        onclick: e => { e.stopPropagation(); setKeyword(k.k); } });
    }));
  }

  // ------------------------------------------------------------ filter bar: one quiet menu per filter
  function filterButton(d) {
    const on = S.f[d.key].length > 0, open = S.menu === d.key, label = d.label.toLowerCase();
    return el("span", { class: "fm" + (on ? " on" : "") + (open ? " open" : "") },
      el("button", { class: "q", "aria-haspopup": "true", "aria-expanded": String(open), "data-focus": `q-${d.key}`, title: on ? `${d.label}: ${shownAs(d, true)}` : null,
          onclick: e => { e.stopPropagation(); toggleMenu(d.key); } },
        el("span", { class: "ql", text: d.label }), el("span", { class: "qv", text: shownAs(d) })),
      on ? el("button", { class: "qx", title: `Clear ${label}`, "aria-label": `Clear ${label}`, text: "×",
        onclick: e => { e.stopPropagation(); setFilter(d.key, d.single ? "" : []); } }) : null,
      open ? filterMenu(d) : null);
  }
  function filterMenu(d) {
    const menu = el("div", { class: "menu", role: "menu", "aria-label": d.label, onclick: e => e.stopPropagation() });
    let items = d.options;
    if (d.find) {
      menu.append(el("input", { class: "mfind", type: "search", placeholder: "Find a keyword", value: S.menuFind, "data-focus": "mfind",
        "aria-label": "Find a keyword", oninput: e => { S.menuFind = e.target.value; renderFilters(); } }));
      const f = S.menuFind.trim().toLowerCase();
      if (f) items = items.filter(([, t]) => t.toLowerCase().includes(f));
    }
    const list = el("div", { class: "mlist" }, items.map(([v, t, c]) => {
      const checked = d.single ? S.f[d.key] === v : S.f[d.key].includes(v);
      return el("button", { class: "mi" + (checked ? " on" : "") + (!c && !checked ? " zero" : ""), role: d.single ? "menuitemradio" : "menuitemcheckbox",
          "aria-checked": String(checked), "data-focus": `mi-${d.key}-${v}`,
          onclick: () => d.single ? setFilter(d.key, checked ? "" : v) : toggleValue(d.key, v) },
        el("span", { class: "box" + (d.single ? " radio" : "") }), el("span", { class: "mt", text: t }), el("span", { class: "n", text: c }));
    }));
    if (!items.length) list.append(el("div", { class: "mnone", text: "No keyword matches" }));
    menu.append(list);
    if (d.key === "added") menu.append(dateRange());
    if (S.f[d.key].length) menu.append(el("div", { class: "mfoot" },
      el("button", { class: "clear", text: "Clear", onclick: () => setFilter(d.key, d.single ? "" : []) })));
    return menu;
  }
  function dateRange() {
    const [, from = "", to = ""] = S.f.added.startsWith("range:") ? S.f.added.split(":") : [];
    const set = (a, b) => setFilter("added", a || b ? `range:${a}:${b}` : "");
    return el("div", { class: "mrange" }, el("div", { class: "mh", text: "Or between" }),
      el("div", { class: "dates" },
        el("input", { type: "date", value: from, max: to || null, "aria-label": "Added on or after", "data-focus": "from", onchange: e => set(e.target.value, to) }),
        el("span", { text: "–" }),
        el("input", { type: "date", value: to, min: from || null, "aria-label": "Added on or before", "data-focus": "to", onchange: e => set(from, e.target.value) })));
  }
  function toggleMenu(key) {
    S.menu = S.menu === key ? null : key; S.menuFind = "";
    renderFilters();
    const first = document.querySelector(".menu .mfind, .menu .mi");
    if (first) first.focus();
  }
  function closeMenu() {
    const key = S.menu;
    S.menu = null; renderFilters();
    const btn = document.querySelector(`[data-focus="q-${key}"]`);
    if (btn) btn.focus();
  }
  // the order is chosen in the date column's header, whose label says which dates the column shows and which way they run
  const SORT_LABEL = { new: "Added ↓", old: "Added ↑", edited: "Changed ↓", az: "A to Z" };
  function renderSort() {
    const col = $("date-col");
    if (S.q) { col.replaceChildren("Added"); return; }  // matches come in order of relevance
    col.replaceChildren(el("span", { class: "fm sort", title: "Change the order" }, el("span", { class: "q" },
      el("span", { class: "qv", text: SORT_LABEL[S.sort] || SORT_LABEL.new }),
      el("select", { "aria-label": "Order", onchange: e => { S.sort = e.target.value; local.set("sort", S.sort); renderList(); } },
        SORTS.map(([v, t]) => el("option", { value: v, text: t, selected: v === S.sort }))))));
  }
  function renderFilters() {
    const was = document.activeElement && document.activeElement.dataset && document.activeElement.dataset.focus;
    const box = $("filters");
    box.replaceChildren(el("div", { class: "frow" }, filterDefs().map(filterButton),
      filtering() > 1 ? el("button", { class: "clear", text: "Clear all", onclick: clearFilters }) : null));
    // the bar is rebuilt on every change: put focus back where it was, and keep an open menu inside the window
    const again = was && box.querySelector(`[data-focus="${CSS.escape(was)}"]`);
    if (again) { again.focus(); if (again.type === "search") again.setSelectionRange(again.value.length, again.value.length); }
    const menu = box.querySelector(".menu");
    if (menu && menu.getBoundingClientRect().right > innerWidth - 8) menu.classList.add("right");
  }
  document.addEventListener("click", e => { if (S.menu && !e.target.closest(".fm")) { S.menu = null; renderFilters(); } });

  // ------------------------------------------------------------ search
  const q = $("q");
  let semTimer = null, semSeq = 0;
  const terms = text => text.toLowerCase().split(/\s+/).filter(Boolean);

  function lexical(query) {
    const ts = terms(query);
    if (!ts.length) return [];
    const scored = [];
    M.forEach((m, i) => {
      const desc = m.description.toLowerCase();
      const hay = `${desc}\n${m.body.toLowerCase()}\n${(m.place || "").toLowerCase()}\n${m.id}\n${m.type}`;
      if (!ts.every(t => hay.includes(t))) return;
      const score = ts.reduce((s, t) => s + (desc.includes(t) ? 10 : 0) + Math.min(5, hay.split(t).length - 1), 0);
      scored.push([score, i]);
    });
    return scored.sort((a, b) => b[0] - a[0] || touched(M[b[1]]).localeCompare(touched(M[a[1]]))).map(([, i]) => i);
  }
  function runSearch(text, semantic = true) {
    S.q = text.trim();
    S.lex = S.q ? lexical(S.q) : [];
    if (!S.q) S.sem = [];
    S.cursor = S.q ? 0 : -1;
    S.semPending = !!(semantic && S.q && D.semantic);

    renderList();
    clearTimeout(semTimer);
    if (!S.semPending) return;
    const seq = ++semSeq, query = S.q;
    semTimer = setTimeout(async () => {
      try {
        const r = await api(`/api/search?q=${encodeURIComponent(query)}`);
        if (seq !== semSeq || query !== S.q) return;
        S.sem = (r.hits || []).filter(h => byId.has(h.id));
      } catch (e) { /* word matches stay */ }
      if (seq === semSeq) { S.semPending = false; renderList(); }
    }, 300);
  }
  function highlight(text, ts) {
    const marks = ts.filter(t => t.length > 1 || /[㐀-鿿]/.test(t));
    const frag = document.createDocumentFragment();
    if (!marks.length) { frag.append(text); return frag; }
    const re = new RegExp(`(${marks.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
    let last = 0;
    text.replace(re, (m, _g, off) => { frag.append(text.slice(last, off), el("mark", { text: m })); last = off + m.length; return m; });
    frag.append(text.slice(last));
    return frag;
  }
  function snippet(m, ts) {
    const desc = m.description.toLowerCase();
    if (ts.every(t => desc.includes(t))) return null;
    const body = m.body.replace(/\s+/g, " "), lower = body.toLowerCase();
    const at = ts.filter(t => !desc.includes(t)).map(t => lower.indexOf(t)).filter(k => k >= 0).sort((a, b) => a - b)[0];
    if (at == null) return null;
    const start = Math.max(0, at - 50);
    return (start ? "…" : "") + body.slice(start, start + 160);
  }
  q.addEventListener("input", () => runSearch(q.value));
  q.addEventListener("keydown", e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); moveCursor(e.key === "ArrowDown" ? 1 : -1); }
    else if (e.key === "Enter") { e.preventDefault(); openCursor(); }
    else if (e.key === "Escape") {
      e.stopPropagation();
      if (q.value) { q.value = ""; runSearch(""); } else q.blur();
    }
  });

  // ------------------------------------------------------------ list
  const list = $("list");
  function sorted(idx) {
    const by = {
      new: (a, b) => (M[b].created || "").localeCompare(M[a].created || ""),
      old: (a, b) => (M[a].created || "").localeCompare(M[b].created || ""),
      edited: (a, b) => touched(M[b]).localeCompare(touched(M[a])),
      az: (a, b) => M[a].description.localeCompare(M[b].description),
    }[S.sort] || (() => 0);
    return idx.sort(by);
  }
  function renderList() {
    if (!D) return;
    const ts = terms(S.q);
    const groups = [];
    if (S.q) {
      const lex = S.lex.filter(i => passes(M[i]));
      const seen = new Set(S.lex);
      const sem = S.sem.map(h => byId.get(h.id)).filter(i => i != null && !seen.has(i) && passes(M[i])).slice(0, 8);
      groups.push([null, lex]);
      if (sem.length) groups.push(["Close in meaning", sem]);
    } else groups.push([null, sorted(M.map((_, i) => i).filter(i => passes(M[i])))]);

    S.rows = groups.flatMap(([, idx]) => idx);
    if (S.cursor >= S.rows.length) S.cursor = S.rows.length - 1;
    const shown = S.rows.length, total = M.length;
    const countEl = $("count");
    S.countText = S.q ? `${plural(groups[0][1].length, "match", "matches")}${groups[1] ? ` + ${groups[1][1].length} close in meaning` : ""}${S.semPending ? " · searching by meaning…" : ""}`
      : shown === total ? plural(total, "memory", "memories") : `${shown} of ${total}`;
    if (countEl) countEl.textContent = S.countText;
    renderSort();

    list.classList.toggle("selecting", S.picked.size > 0);
    const box = $("rows");
    box.replaceChildren();
    let k = 0;
    for (const [title, idx] of groups) {
      if (title && idx.length) box.append(el("div", { class: "group", text: title }));
      for (const i of idx) box.append(row(i, k++, title ? [] : ts));
    }
    if (!shown) {
      const filtered = filtering() > 0;
      box.append(el("div", { class: "empty" },
        el("div", { text: S.q ? (S.semPending ? "No word matches; searching by meaning…" : "No matches.") : "No memories match these filters." }),
        filtered ? el("button", { class: "btn", text: "Clear filters", onclick: clearFilters }) : null));
    }
    renderSelbar();
  }
  function row(i, k, ts) {
    const m = M[i], picked = S.picked.has(m.id);
    const snip = ts.length ? snippet(m, ts) : null;
    return el("div", { class: "row" + (S.open === m.id ? " open" : "") + (picked ? " picked" : "") + (k === S.cursor ? " cursor" : ""),
        "data-k": k, onclick: e => { if (e.metaKey || e.shiftKey) { togglePick(m.id); return; } S.cursor = k; openMemory(m.id); } },
      el("input", { type: "checkbox", class: "chk", "aria-label": "Select", checked: picked,
        onclick: e => { e.stopPropagation(); togglePick(m.id); } }),
      el("div", { class: "main" },
        el("div", { class: "desc" }, highlight(m.description, ts)),
        snip ? el("div", { class: "snip" }, highlight(snip, ts)) : keywordChips(m)),
      el("span", { class: "c-type" }, el("i", { class: `dot ${m.type}` }), m.type),
      el("span", { class: "c-place", title: m.scope === "global" ? "Loads in every session" : m.place, text: m.scope === "global" ? "everywhere" : m.place }),
      el("span", { class: "c-date", title: m.updated ? `added ${day(m.created)}, changed ${day(m.updated)}` : `added ${day(m.created)}`, text: day(S.sort === "edited" ? touched(m) : m.created) }));
  }
  function moveCursor(step) {
    if (!S.rows.length) return;
    S.cursor = Math.max(0, Math.min(S.rows.length - 1, (S.cursor < 0 ? (step > 0 ? -1 : S.rows.length) : S.cursor) + step));
    list.querySelectorAll(".row").forEach(r => r.classList.toggle("cursor", Number(r.dataset.k) === S.cursor));
    const r = list.querySelector(`.row[data-k="${S.cursor}"]`);
    if (r) r.scrollIntoView({ block: "nearest" });
    if (S.open && S.mode === "view") openMemory(M[S.rows[S.cursor]].id);  // reading along
  }
  function openCursor() { if (S.cursor >= 0 && S.rows[S.cursor] != null) openMemory(M[S.rows[S.cursor]].id); }

  // ------------------------------------------------------------ selection
  function togglePick(id) { S.picked.has(id) ? S.picked.delete(id) : S.picked.add(id); renderList(); }
  function renderSelbar() {
    const bar = $("selbar");
    bar.hidden = !S.picked.size;
    if (!S.picked.size) return;
    const shown = S.rows.map(i => M[i].id), rest = shown.filter(id => !S.picked.has(id)).length;
    bar.replaceChildren(
      el("span", { class: "n", text: `${S.picked.size} selected` }),
      rest ? el("button", { class: "btn", text: `Select all ${shown.length} shown`, onclick: () => { shown.forEach(id => S.picked.add(id)); renderList(); } }) : null,
      el("button", { class: "btn", text: "Clear", onclick: () => { S.picked.clear(); renderList(); } }),
      el("button", { class: "btn danger", text: "Delete", onclick: () => deleteMany([...S.picked]) }));
  }
  async function deleteMany(ids) {
    const ms = ids.map(id => M[byId.get(id)]).filter(Boolean);
    if (!ms.length) return;
    const text = ms.length === 1 ? `Delete this memory?\n\n${ms[0].description}`
      : `Delete ${ms.length} memories?\n\n` + ms.slice(0, 10).map(m => `• ${m.description}`).join("\n") + (ms.length > 10 ? `\n…and ${ms.length - 10} more` : "");
    if (!confirm(text)) return;
    try {
      const r = await api("/api/delete", { items: ms.map(m => ({ id: m.id, base: m.hash })) });
      ms.forEach(m => S.picked.delete(m.id));
      if (S.open && ms.some(m => m.id === S.open)) closeDrawer(true);
      await reload();
      toast(ms.length === 1 ? "Memory deleted" : `${ms.length} memories deleted`, { undo: r.commit });
    } catch (e) { toast(e.message, { error: true }); }
  }

  // ------------------------------------------------------------ markdown
  const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\[\[[^\]]+\]\])|(\[[^\]]+\]\((?:https?:\/\/)[^)\s]+\))|(\*[^*\s][^*]*\*)|(https?:\/\/[^\s<>()]+)/g;
  function inline(parent, text) {
    let last = 0;
    for (const m of text.matchAll(INLINE)) {
      parent.append(text.slice(last, m.index));
      const s = m[0];
      if (m[1]) parent.append(el("code", { text: s.slice(1, -1) }));
      else if (m[2]) { const b = el("strong"); inline(b, s.slice(2, -2)); parent.append(b); }
      else if (m[3]) {
        const name = s.slice(2, -2), target = byName.get(name);
        parent.append(target != null
          ? el("span", { class: "wikilink", role: "link", tabindex: "0", text: name, onclick: () => pick(M[target].id) })
          : el("span", { text: s }));
      } else if (m[4]) {
        const mm = s.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
        parent.append(el("a", { href: mm[2], target: "_blank", rel: "noopener noreferrer", text: mm[1] }));
      } else if (m[5]) { const i = el("em"); inline(i, s.slice(1, -1)); parent.append(i); }
      else if (m[6]) parent.append(el("a", { href: s, target: "_blank", rel: "noopener noreferrer", text: s }));
      last = m.index + s.length;
    }
    parent.append(text.slice(last));
  }
  const LIST = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
  function parseList(lines, i) {
    const first = lines[i].match(LIST), indent = first[1].length;
    const list = el(/\d/.test(first[2]) ? "ol" : "ul");
    while (i < lines.length) {
      const m = lines[i].match(LIST);
      if (!m) {
        if (lines[i].trim() && /^\s+/.test(lines[i]) && list.lastElementChild) { list.lastElementChild.append(" "); inline(list.lastElementChild, lines[i].trim()); i++; continue; }
        if (!lines[i].trim() && i + 1 < lines.length && (lines[i + 1].match(LIST) || [])[1] != null && lines[i + 1].match(LIST)[1].length >= indent) { i++; continue; }
        break;
      }
      if (m[1].length < indent) break;
      if (m[1].length > indent) { const sub = parseList(lines, i); (list.lastElementChild || list).append(sub.node); i = sub.next; continue; }
      const li = el("li"); inline(li, m[3]); list.append(li); i++;
    }
    return { node: list, next: i };
  }
  function markdown(src) {
    const root = el("div", { class: "md" });
    const lines = src.replace(/\r\n?/g, "\n").split("\n");
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) { i++; continue; }
      let m = line.match(/^\s*(```+|~~~+)/);
      if (m) {
        const buf = []; i++;
        while (i < lines.length && !lines[i].trim().startsWith(m[1])) buf.push(lines[i++]);
        i++;
        root.append(el("pre", {}, el("code", { text: buf.join("\n") })));
        continue;
      }
      m = line.match(/^(#{1,6})\s+(.*)$/);
      if (m) { const h = el("h" + Math.min(4, m[1].length)); inline(h, m[2]); root.append(h); i++; continue; }
      if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { root.append(el("hr")); i++; continue; }
      if (/^\s*>/.test(line)) {
        const buf = [];
        while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ""));
        root.append(el("blockquote", {}, markdown(buf.join("\n"))));
        continue;
      }
      if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
        const cells = l => l.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
        const table = el("table"), head = el("tr");
        cells(line).forEach(c => { const th = el("th"); inline(th, c); head.append(th); });
        table.append(el("thead", {}, head));
        const tbody = el("tbody");
        i += 2;
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
          const tr = el("tr"); cells(lines[i++]).forEach(c => { const td = el("td"); inline(td, c); tr.append(td); }); tbody.append(tr);
        }
        table.append(tbody); root.append(table);
        continue;
      }
      if (LIST.test(line)) { const r = parseList(lines, i); root.append(r.node); i = r.next; continue; }
      const buf = [];
      while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|\s*(```|~~~)|\s*>)/.test(lines[i]) && !LIST.test(lines[i])) buf.push(lines[i++]);
      const p = el("p"); inline(p, buf.join(" ")); root.append(p);
    }
    return root;
  }

  // ------------------------------------------------------------ drawer
  const drawer = $("drawer");
  const TYPE_HELP = { user: "who you are", feedback: "how you want work done", project: "facts about a project", reference: "where to find things" };

  function pick(id) { openMemory(id); }
  function showDrawer(on) {
    drawer.classList.toggle("open", on); drawer.setAttribute("aria-hidden", String(!on));
    document.body.classList.toggle("drawer-open", on);
  }
  function openMemory(id) {
    if (S.mode !== "view" && dirty() && !confirm("Discard your unsaved changes?")) return;
    S.open = id; S.mode = "view";
    const k = S.rows.indexOf(byId.get(id));
    if (k >= 0) S.cursor = k;
    renderDrawer();
    showDrawer(true);
    list.querySelectorAll(".row").forEach(r => {
      const on = S.rows[Number(r.dataset.k)] === byId.get(id);
      r.classList.toggle("open", on); r.classList.toggle("cursor", Number(r.dataset.k) === S.cursor);
      if (on) r.scrollIntoView({ block: "nearest" });
    });
  }
  function closeDrawer(force) {
    if (!force && S.mode !== "view" && dirty() && !confirm("Discard your unsaved changes?")) return;
    S.open = null; S.mode = "view";
    showDrawer(false);
    list.querySelectorAll(".row.open").forEach(r => r.classList.remove("open"));
  }
  function startNew() {
    if (S.mode !== "view" && dirty() && !confirm("Discard your unsaved changes?")) return;
    S.open = null; S.mode = "new";
    S.draft = { description: "", type: "feedback", scope: "global", place: null, path: "", body: "" };
    S.base = { ...S.draft };
    renderDrawer();
    showDrawer(true);
    setTimeout(() => { const t = drawer.querySelector("textarea.desc"); if (t) t.focus(); }, 60);
  }
  function startEdit() {
    const m = M[byId.get(S.open)];
    S.mode = "edit";
    S.draft = { description: m.description, type: m.type, scope: m.scope, place: m.scope === "here" ? m.place : null, path: "", body: m.body };
    S.base = { ...S.draft };
    renderDrawer();
  }
  const dirty = () => S.draft && JSON.stringify(S.draft) !== JSON.stringify(S.base);

  function renderDrawer() {
    drawer.replaceChildren();
    if (S.mode === "view") return renderView();
    return renderForm();
  }
  function propsList(meta) {
    const dl = el("dl", { class: "props" });
    const show = v => Array.isArray(v) ? (v.length ? v.join(", ") : "[]") : v === null ? "null" : String(v);
    for (const [k, v] of Object.entries(meta)) {
      if (v && typeof v === "object" && !Array.isArray(v)) {
        dl.append(el("div", { class: "sect", text: k }));
        for (const [k2, v2] of Object.entries(v)) dl.append(el("dt", { text: k2 }), el("dd", { text: show(v2) }));
      } else dl.append(el("dt", { text: k }), el("dd", { text: show(v) }));
    }
    return dl;
  }
  function renderView() {
    const i = byId.get(S.open);
    if (i == null) return;
    const m = M[i];
    const head = el("div", { class: "d-head" },
      el("div", { class: "d-bar" },
        el("span", { class: "where", title: m.path, text: `memories/${m.rel}` }),
        iconBtn("copy", "Copy file path", () => copyText(m.path, "Path copied")),
        iconBtn("edit", "Edit (e)", startEdit),
        iconBtn("trash", "Delete", () => deleteMany([m.id])),
        iconBtn("close", "Close (Esc)", () => closeDrawer())),
      el("h1", { text: m.description }),
      el("div", { class: "d-meta" },
        el("span", { title: TYPE_HELP[m.type] }, el("i", { class: `dot ${m.type}` }), m.type),
        el("span", { class: "sep", text: "·" }),
        el("span", { text: m.scope === "global" ? "loads everywhere" : `loads in ${m.place || "one place"}` }),
        el("span", { class: "sep", text: "·" }),
        el("span", { text: m.updated ? `changed ${day(m.updated)}` : `added ${day(m.created)}` })),
      keywordChips(m),
      (m.issues || []).length ? el("ul", { class: "issues", title: "Differs from the format in PROTOCOL.md" }, m.issues.map(t => el("li", { text: t.replace(/\*\*([^*]+?):?\*\*/g, "“$1”") }))) : null,
      el("div", { class: "tabs", role: "tablist" },
        ["rendered", "file"].map(t => el("button", { role: "tab", "aria-selected": String(S.tab === t), text: t === "rendered" ? "Memory" : "File",
          onclick: () => { S.tab = t; renderDrawer(); } }))));
    const body = el("div", { class: "d-body" });
    if (S.tab === "file") body.append(el("pre", { class: "raw", text: m.raw }));
    else {
      body.append(markdown(m.body), el("div", { class: "section" }, el("h2", { text: "Details" }), propsList(m.meta)));
      const sim = m.similar.filter(s => s.s > 0.05).slice(0, 5);
      if (sim.length) body.append(el("div", { class: "section similar" }, el("h2", { text: "Similar memories" }),
        sim.map(s => el("button", { onclick: () => pick(M[s.i].id) }, el("span", { class: "t", text: M[s.i].description }),
          el("span", { class: "p", text: `${Math.round(s.s * 100)}%` })))));
    }
    drawer.append(head, body);
  }

  function renderForm() {
    const d = S.draft, isNew = S.mode === "new";
    const counter = el("span", { class: "hint" });
    const count = () => { counter.textContent = `${d.description.length} / 150`; counter.classList.toggle("over", d.description.length > 150); };
    const desc = el("textarea", { class: "desc", rows: 2, placeholder: "One line: what should an agent know?", value: d.description,
      oninput: e => { d.description = e.target.value; count(); } });
    count();
    const typeSel = el("select", { onchange: e => { d.type = e.target.value; typeHint.textContent = TYPE_HELP[d.type]; } },
      TYPES.map(t => el("option", { value: t, text: t, selected: d.type === t })));
    const typeHint = el("span", { class: "hint", text: TYPE_HELP[d.type] });
    const placeRow = el("div");
    const drawPlace = () => {
      placeRow.replaceChildren();
      if (d.scope !== "here") return;
      const options = (D.places || []).map(p => p.key);
      if (d.place && !options.includes(d.place)) options.unshift(d.place);
      const sel = el("select", { onchange: e => {
          d.pathMode = e.target.value === "__path";
          d.place = d.pathMode ? null : e.target.value;
          drawPlace();
        } },
        el("option", { value: "", text: "Choose a place…", disabled: true, selected: !d.place && !d.pathMode }),
        options.map(o => el("option", { value: o, text: o, selected: d.place === o })),
        el("option", { value: "__path", text: "Another folder…", selected: !d.place && d.pathMode }));
      placeRow.append(el("label", {}, "Place", sel));
      if (d.pathMode) placeRow.append(el("label", { style: "margin-top:8px" }, "Folder path",
        el("input", { type: "text", value: d.path, placeholder: "~/repos/project", oninput: e => { d.path = e.target.value; } })));
    };
    const seg = el("div", { class: "seg" }, [["global", "Everywhere"], ["here", "One place"]].map(([v, l]) =>
      el("button", { type: "button", "aria-pressed": String(d.scope === v), text: l, onclick: () => {
        d.scope = v; seg.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b.textContent === l))); drawPlace(); } })));
    drawPlace();
    const bodyArea = el("textarea", { class: "body", spellcheck: "false", value: d.body,
      placeholder: "The fact itself.\n\n**Why:** …\n\n**How to apply:** …", oninput: e => { d.body = e.target.value; } });
    const err = el("span", { class: "err" });
    const save = el("button", { class: "btn primary", text: isNew ? "Add memory" : "Save", title: "⌘S", onclick: () => submit(err) });
    drawer.append(
      el("div", { class: "d-head" }, el("div", { class: "d-bar" },
        el("span", { class: "where", text: isNew ? "New memory" : `Editing · memories/${M[byId.get(S.open)].rel}` }),
        iconBtn("close", "Cancel (Esc)", () => isNew ? closeDrawer() : cancelEdit()))),
      el("div", { class: "d-body" }, el("div", { class: "form" },
        el("label", {}, el("span", { style: "display:flex;justify-content:space-between" }, "Description", counter), desc),
        el("div", { class: "pair" }, el("label", {}, el("span", { style: "display:flex;justify-content:space-between" }, "Type", typeHint), typeSel),
          el("label", {}, "Loads", seg)),
        placeRow,
        el("label", {}, "Memory (Markdown)", bodyArea))),
      el("div", { class: "d-foot" }, err, el("button", { class: "btn", text: "Cancel", onclick: () => isNew ? closeDrawer() : cancelEdit() }), save));
  }
  function cancelEdit() {
    if (dirty() && !confirm("Discard your unsaved changes?")) return;
    S.mode = "view"; renderDrawer();
  }
  async function submit(err) {
    const d = S.draft;
    err.textContent = "";
    if (!d.description.trim()) { err.textContent = "Add a one-line description."; return; }
    let place = null;
    if (d.scope === "here") {
      if (d.pathMode) { if (!d.path.trim()) { err.textContent = "Type the folder path."; return; } place = { path: d.path.trim() }; }
      else if (d.place) place = { key: d.place };
      else { err.textContent = "Choose where it loads."; return; }
    }
    try {
      if (S.mode === "new") {
        const r = await api("/api/create", { type: d.type, scope: d.scope, description: d.description, body: d.body, place });
        S.mode = "view"; S.draft = null; S.open = r.id;
        await reload();
        openMemory(r.id);
        toast("Memory added", { undo: r.commit });
      } else {
        const m = M[byId.get(S.open)], change = {};
        if (d.description !== m.description) change.description = d.description;
        if (d.type !== m.type) change.type = d.type;
        if (d.scope !== m.scope) change.scope = d.scope;
        if (d.body !== m.body) change.body = d.body;
        if (place && (place.path || place.key !== m.place)) change.place = place;
        const r = await api("/api/edit", { id: m.id, base: m.hash, change });
        S.mode = "view"; S.draft = null;
        await reload();
        renderDrawer();
        if (r.commit) toast("Saved", { undo: r.commit });
      }
    } catch (e) { err.textContent = e.message; }
  }
  async function copyText(text, done) {
    try { await navigator.clipboard.writeText(text); toast(done); } catch (e) { prompt("Copy:", text); }
  }

  // ------------------------------------------------------------ chrome
  function renderStatus() {
    $("repo").textContent = D.dataDir || "";
    $("repo").title = "Data repository";
    const g = D.sync || {};
    $("status").replaceChildren(g.remote && g.ahead
      ? el("span", { class: "warn", title: "Commits that a hook or this page made but has not pushed yet" }, el("i", { class: "dot" }), `${plural(g.ahead, "change")} not pushed`)
      : "");
  }
  $("new").addEventListener("click", startNew);
  document.addEventListener("keydown", e => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) && document.activeElement.type !== "checkbox";
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s" && S.mode !== "view") {
      e.preventDefault(); const btn = drawer.querySelector(".d-foot .btn.primary"); if (btn) btn.click(); return;
    }
    if (e.key === "Escape") {
      if (S.menu) { closeMenu(); return; }
      if (typing) { document.activeElement.blur(); return; }
      if (S.mode === "edit") return cancelEdit();
      if (S.open || S.mode === "new") return closeDrawer();
      if (S.picked.size) { S.picked.clear(); renderList(); return; }
      if (S.q) { q.value = ""; runSearch(""); }
      return;
    }
    if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "/") { e.preventDefault(); q.focus(); q.select(); }
    else if (e.key === "n") { e.preventDefault(); startNew(); }
    else if (e.key === "e" && S.open && S.mode === "view") { e.preventDefault(); startEdit(); }
    else if ((e.key === "j" || e.key === "ArrowDown") && S.mode === "view") { e.preventDefault(); moveCursor(1); }
    else if ((e.key === "k" || e.key === "ArrowUp") && S.mode === "view") { e.preventDefault(); moveCursor(-1); }
    else if (e.key === "Enter" && S.mode === "view") { e.preventDefault(); openCursor(); }
    else if (e.key === "x" && S.cursor >= 0 && S.rows[S.cursor] != null) { e.preventDefault(); togglePick(M[S.rows[S.cursor]].id); }
  });
  addEventListener("beforeunload", e => { if (S.mode !== "view" && dirty()) { e.preventDefault(); e.returnValue = ""; } });

  // pick up memories that agents write while the page is open
  setInterval(async () => {
    if (document.hidden || !D || S.mode !== "view") return;
    try { const st = await api("/api/stamp"); if (st.stamp !== D.stamp) await reload(); } catch (e) { /* server stopped */ }
  }, 20000);

  (async () => {
    const boot = $("boot");
    if (!token) { boot.textContent = "Open this page with the link that `mem ui` prints."; return; }
    try { await reload(); boot.remove(); }
    catch (e) { boot.textContent = e.status === 401 ? "This link has expired. Run `mem ui` again and use the new link." : `Could not load memories: ${e.message}`; }
  })();
})();
