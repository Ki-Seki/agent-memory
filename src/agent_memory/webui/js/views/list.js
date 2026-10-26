// The list pane: search, filters, and each memory as its description and one line of type, place and date.
import { addedOptions, SORTS, touched } from "../filters.js";
import { day, placeShort } from "../format.js";
import { attrs, cx, html } from "../h.js";
import { icon } from "../icons.js";
import { highlight, snippet, terms } from "../search.js";
import { app } from "../store.js";
import { unpushed } from "./shell.js";
import { checkbox, kbd, menu, typeDot } from "./ui.js";

function searchBox() {
  return html`<label class="search">
    ${icon("search")}
    <input id="q" type="search" placeholder="Search memories" autocomplete="off" spellcheck="false" data-input="search"${attrs({ value: app.q })}>
    <span class="search-end">${app.q ? html`<button type="button" class="clear" aria-label="Clear search" data-act="clearSearch">${icon("x")}</button>` : kbd("/")}</span>
  </label>${app.demo && !app.q ? html`<div class="try"><span>Try</span>${app.demo.queries.map((q) => html`<button type="button" data-act="trySearch" data-arg="${q}">${q}</button>`)}</div>` : ""}`;
}

// ---------------------------------------------------------------- filters

/** Types as a row of toggles: any number can be on; All turns them all off. */
function typeToggle(def) {
  const on = app.filters.type;
  return html`<div class="type-toggle" role="group" aria-label="Type">
    <button type="button" aria-pressed="${!on.length}" data-act="setList" data-arg="type">All</button>
    ${def.options.map((o) => html`<button type="button"${attrs({ "aria-pressed": String(on.includes(o.value)), class: !o.count && !on.includes(o.value) ? "faint" : null, title: `${o.count} ${o.value}`, "data-act": "toggle", "data-arg": `type:${o.value}` })}>${typeDot(o.value)}<span>${o.label}</span></button>`)}
  </div>`;
}

/** A filter chip: a quiet button that opens its menu, with an x to clear it once set. */
function chip(key, label, shown, set, title, content, cls = "") {
  const id = `menu-${key}`;
  return html`<span class="${cx("chip", set && "set")}">
    <button type="button" class="chip-btn"${attrs({ popovertarget: id, title })}>${label} <span class="chip-value">${shown}</span>${set ? "" : icon("chevron-down")}</button>
    ${set ? html`<button type="button" class="chip-x"${attrs({ "aria-label": `Clear ${label.toLowerCase()}`, "data-act": key === "added" ? "setAdded" : "setList", "data-arg": key === "added" ? "" : key })}>${icon("x")}</button>` : ""}
    ${menu(id, content, cls)}
  </span>`;
}

/** One filter whose menu is a checklist: tick any number of values. */
function facet(def) {
  const values = app.filters[def.key];
  const name = (v) => def.options.find((o) => o.value === v)?.label ?? v;
  const short = (v) => (v.startsWith("place:") ? placeShort(v.slice(6)) : name(v));
  const shown = !values.length ? def.any : values.length === 1 ? short(values[0]) : `${short(values[0])} +${values.length - 1}`;
  const q = def.search ? app.menuQuery.trim().toLowerCase() : "";
  const options = q ? def.options.filter((o) => o.label.toLowerCase().includes(q) || o.value.includes(q)) : def.options;
  const content = html`
    ${def.search ? html`<input class="menu-find" type="text" placeholder="Find a ${def.label.toLowerCase()}" data-input="menuQuery"${attrs({ value: app.menuQuery })}>` : ""}
    <div class="menu-list" role="menu">
      ${options.length ? "" : html`<p class="menu-empty">Nothing matches.</p>`}
      ${options.map((o) => {
        const on = values.includes(o.value);
        return html`<button type="button" role="menuitemcheckbox" class="${cx("menu-item", !o.count && !on && "faint")}"${attrs({ "aria-checked": String(on), "data-act": "toggle", "data-arg": `${def.key}:${o.value}`, "data-key": `${def.key}:${o.value}` })}>
          <span class="tick">${on ? icon("check", "", 3) : ""}</span><span class="grow truncate"${attrs({ title: o.label })}>${o.label}</span><span class="count">${o.count}</span></button>`;
      })}
    </div>
    ${values.length ? html`<div class="menu-foot"><button type="button" class="menu-wide" data-act="setList" data-arg="${def.key}">Clear ${def.label.toLowerCase()}</button></div>` : ""}`;
  return chip(def.key, def.label, shown, values.length > 0, values.length ? `${def.label}: ${values.map(name).join(", ")}` : null, content);
}

/** When a memory was added: one recent period, or a date range with either end open. */
function added() {
  const v = app.filters.added;
  const opts = addedOptions(app.M, app.filters, app.termSets);
  const range = v.startsWith("range:") ? v.split(":").slice(1) : ["", ""];
  const fmt = (s) => new Date(`${s}T00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  const shown = !v ? "Any time"
    : v.startsWith("range:") ? (range[0] && range[1] ? `${fmt(range[0])} – ${fmt(range[1])}` : range[0] ? `since ${fmt(range[0])}` : `until ${fmt(range[1])}`)
    : (opts.find((o) => o.value === v)?.label ?? v);
  const content = html`
    <div class="menu-list" role="radiogroup" aria-label="Added">
      ${opts.map((o) => {
        const on = v === o.value;
        return html`<button type="button" role="radio" class="${cx("menu-item", !o.count && !on && "faint")}"${attrs({ "aria-checked": String(on), "data-act": "setAdded", "data-arg": on ? "" : o.value })}>
          <span class="radio">${on ? html`<i></i>` : ""}</span><span class="grow truncate"${attrs({ title: o.label })}>${o.label}</span><span class="count">${o.count}</span></button>`;
      })}
    </div>
    <div class="menu-range">
      <div class="menu-note">Or between</div>
      <div class="range">
        <input type="date" aria-label="Added on or after" data-change="rangeFrom"${attrs({ value: range[0], max: range[1] || null })}>
        –
        <input type="date" aria-label="Added on or before" data-change="rangeTo"${attrs({ value: range[1], min: range[0] || null })}>
      </div>
    </div>
    ${v ? html`<div class="menu-foot"><button type="button" class="menu-wide" data-act="setAdded" data-arg="">Any time</button></div>` : ""}`;
  return chip("added", "Added", shown, !!v, null, content);
}

function filterBar() {
  const typeDef = app.filterDefs.find((d) => d.key === "type");
  const facets = app.filterDefs.filter((d) => d.key !== "type");
  // the type toggles need about 328px; a narrower list shows Type as a menu like the other filters
  return html`<div class="filters">
    <div class="wide-only">${typeToggle(typeDef)}</div>
    <div class="chips">
      <span class="narrow-only">${facet(typeDef)}</span>
      ${facets.filter((d) => d.key !== "status").map(facet)}
      ${added()}
      ${facets.filter((d) => d.key === "status").map(facet)}
      ${app.filtering > 1 ? html`<button type="button" class="clear-all" data-act="clearFilters">Clear all</button>` : ""}
    </div>
  </div>`;
}

// ---------------------------------------------------------------- the list

/** The order, chosen where the dates are: the label says which dates and which way they run. */
function sortMenu() {
  if (app.q.trim()) return html`<span>Added</span>`;
  const label = { new: "Added", old: "Added", edited: "Changed", az: "A to Z" }[app.sort];
  const arrow = app.sort === "old" ? icon("arrow-up") : app.sort !== "az" ? icon("arrow-down") : "";
  return html`<button type="button" class="sort-btn" popovertarget="menu-sort" title="Change the order">${label}${arrow}</button>
    ${menu("menu-sort", html`<div class="menu-list" role="menu">${SORTS.map(([value, text]) => html`<button type="button" role="menuitemradio" class="menu-item"${attrs({ "aria-checked": String(app.sort === value), "data-act": "setSort", "data-arg": value })}><span class="grow">${text}</span>${app.sort === value ? icon("check", "accent") : ""}</button>`)}</div>`, "narrow", "end")}`;
}

function row(m, words) {
  const k = app.rows.indexOf(m);
  const isOpen = app.openId === m.id;
  const picked = app.picked.has(m.id);
  const snip = words.length ? snippet(m, words) : null;
  const place = m.scope === "global" ? "Everywhere" : placeShort(m.place);
  const date = day(app.sort === "edited" ? touched(m) : m.created);
  return html`<div role="button" tabindex="-1"${attrs({ class: cx("row", picked && "picked", isOpen && "open", !isOpen && k === app.cursor && "cursor"), "data-k": k, "data-key": `row-${m.id}`, "data-act": "row", "data-arg": m.id })}>
    <span class="${cx("row-check", (app.picked.size > 0 || picked) && "shown")}">${checkbox(picked, "Select", "pick", m.id)}</span>
    <div class="row-main">
      <div class="row-title">${highlight(m.description, words)}</div>
      <div class="row-meta">${typeDot(m.type, true)}<span>·</span><span class="truncate"${attrs({ title: m.scope === "global" ? "Loads in every session" : m.place })}>${place}</span><span>·</span><span class="nowrap">${date}</span></div>
      ${snip ? html`<div class="row-snip">${highlight(snip, words)}</div>` : ""}
    </div>
  </div>`;
}

function list() {
  const words = terms(app.q);
  let empty = "";
  if (!app.rows.length) {
    const text = app.q.trim() ? (app.semPending ? "No word matches; searching by meaning…" : "No matches.")
      : app.M.length ? "No memories match these filters." : "No memories yet. Agents add them as you work.";
    empty = html`<div class="list-empty"><p>${text}</p>${app.filtering ? html`<button type="button" class="btn" data-act="clearFilters">Clear filters</button>` : ""}</div>`;
  }
  return html`<div class="list-bar"><span aria-live="polite">${app.countText}</span>${sortMenu()}</div>
    ${app.groups.map((g, gi) => html`${g.title && g.items.length ? html`<div class="list-group" data-key="group-${gi}">${g.title}</div>` : ""}${g.items.map((m) => row(m, words))}`)}
    ${empty}`;
}

export function listPane() {
  return html`<section class="list-pane" data-key="list-pane">
    <div role="separator" aria-orientation="vertical" aria-label="Resize the list" tabindex="0" class="resize" data-resize title="Drag to resize; double-click to reset"><span></span></div>
    <div class="list-head">
      <h1>Memories <span>${app.M.length}</span></h1>
      <button type="button" class="btn primary sm" data-act="startNew" title="New memory (n)">${icon("plus")}New</button>
    </div>
    <div class="list-tools">${searchBox()}${filterBar()}</div>
    <div class="list-scroll" data-key="list-scroll">${list()}</div>
    ${app.unpushed ? html`<div class="list-foot">${unpushed()}</div>` : ""}
  </section>`;
}
