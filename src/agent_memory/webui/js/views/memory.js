// Where a memory opens: the memory itself, its edit form, or the new-memory form.
import { TYPE_HELP, TYPES } from "../filters.js";
import { longDay } from "../format.js";
import { attrs, cx, html } from "../h.js";
import { icon } from "../icons.js";
import { parse, renderBlocks } from "../markdown.js";
import { app } from "../store.js";
import { iconButton, segmented, select, typeDot } from "./ui.js";

const SOURCE = [["tool", "Written by"], ["session_name", "Session"], ["session_id", "Session id"], ["model", "Model"], ["host", "Host"], ["cwd", "Folder"], ["git_remote", "Repository"], ["git_branch", "Branch"], ["git_commit", "Commit"]];

/** A [[link]] to another memory by name, or the name as written when no memory has it. */
const wiki = (name) => {
  const m = app.byName.get(name);
  return m ? html`<a href="#/memories/${encodeURIComponent(m.id)}" data-act="openName" data-arg="${name}">${name}</a>` : html`<span title="No memory has this name">[[${name}]]</span>`;
};

const pairs = (list) => html`<dl class="pairs">${list.map(([k, v]) => html`<dt>${k}</dt><dd>${v}</dd>`)}</dl>`;

/** One memory: what it says first, then where it came from, the rest of its frontmatter, and similar memories. */
function detail(m) {
  const source = m.meta.source ?? {};
  const provenance = SOURCE.map(([k, label]) => [label, String(source[k] ?? "")]).filter(([, v]) => v);
  const details = Object.entries(m.meta).filter(([k]) => !["source", "description", "type", "scope"].includes(k)).map(([k, v]) => [k, Array.isArray(v) ? v.join(", ") : String(v)]);
  const similar = m.similar.filter((s) => s.s > 0.05).slice(0, 5).map((s) => ({ m: app.M[s.i], s: s.s })).filter((x) => x.m);
  const show = (text) => text.replace(/\*\*([^*]+?):?\*\*/g, "“$1”");
  const tab = (v, label) => html`<button type="button" role="tab"${attrs({ "aria-selected": String(app.tab === v), "data-act": "tab", "data-arg": v })}>${label}</button>`;
  return html`<article class="memory" data-key="memory-${m.id}">
    <div class="memory-bar">
      <span class="file-path" title="${m.path}">memories/${m.rel}</span>
      ${iconButton("copy", "Copy file path", "copyPath")}
      ${iconButton("pencil", "Edit (e)", "startEdit")}
      ${iconButton("trash", "Delete", "removeOpen")}
    </div>
    <h1 class="memory-title">${m.description}</h1>
    <div class="memory-meta">
      <span data-tip="${TYPE_HELP[m.type]}">${typeDot(m.type, true)}</span>
      <span class="sep">·</span>
      <span class="where">${m.scope === "global" ? html`${icon("globe")}Loads everywhere` : html`${icon("folder")}<span class="truncate">${m.place}</span>`}</span>
      <span class="sep">·</span>
      <span>Added ${longDay(m.created)}</span>
      ${m.updated ? html`<span class="faint">· changed ${longDay(m.updated)}</span>` : ""}
    </div>
    ${m.keywords.length ? html`<div class="keywords">${m.keywords.map((k) => {
      const on = app.filters.kw.includes(k.k);
      return html`<button type="button"${attrs({ class: cx("kw", on && "on"), title: on ? `Stop filtering by ${k.t}` : `Only memories that mention ${k.t}`, "data-act": "toggle", "data-arg": `kw:${k.k}` })}>${k.t}</button>`;
    })}</div>` : ""}
    ${m.issues.length ? html`<div class="callout warn">${icon("triangle-alert")}<div><div class="callout-title">Differs from the format in PROTOCOL.md</div>
      <ul>${m.issues.map((issue) => html`<li>${show(issue)}</li>`)}</ul></div></div>` : ""}
    <div class="tabs" role="tablist">${tab("memory", "Memory")}${tab("file", "File")}</div>
    ${app.tab === "file" ? html`<pre class="raw">${m.raw}</pre>` : html`
      <div class="md">${renderBlocks(parse(m.body), wiki)}</div>
      ${provenance.length ? html`<section class="facts"><h2>Provenance</h2>${pairs(provenance)}</section>` : ""}
      <section class="facts"><h2>Details</h2>${pairs(details)}</section>
      ${similar.length ? html`<section class="facts similar"><h2>Similar</h2>${similar.map((x) => html`<button type="button" data-act="open" data-arg="${x.m.id}"><span class="grow">${x.m.description}</span><span class="count">${Math.round(x.s * 100)}%</span></button>`)}</section>` : ""}`}
  </article>`;
}

const OTHER = "__folder";

function form() {
  const d = app.draft;
  const isNew = app.mode === "new";
  const placeItems = [
    ...(d.place && !app.places.some((p) => p.key === d.place) ? [{ value: d.place, label: d.place }] : []),
    ...app.places.map((p) => ({ value: p.key, label: p.key })),
    { value: OTHER, label: "Another folder…" },
  ];
  return html`<form class="memory-form" data-memory-form data-key="${isNew ? "form-new" : `form-${app.openId}`}">
    <div class="memory-bar">
      <span class="file-path">${isNew ? "New memory" : `Editing · memories/${app.open?.rel}`}</span>
      ${iconButton("x", "Cancel (Esc)", "cancelEdit")}
    </div>
    <div class="fields">
      <label class="field">
        <span class="field-label">Description <span class="${cx("hint", d.description.length > 150 && "bad")}">${d.description.length} / 150</span></span>
        <textarea id="f-desc" rows="2" class="input desc" placeholder="One line: what should an agent know?" data-input="draft:description">${d.description}</textarea>
      </label>
      <div class="field">
        <div class="field-label">Type <span class="hint">${TYPE_HELP[d.type]}</span></div>
        <div class="caps">${segmented("Type", d.type, TYPES.map((t) => ({ value: t, label: t })), "draftType", (v) => typeDot(v))}</div>
      </div>
      <div class="field">
        <div class="field-label">Loads</div>
        <div class="row-wrap">
          ${segmented("Loads", d.scope, [{ value: "global", label: "Everywhere" }, { value: "here", label: "One place" }], "draftScope")}
          ${d.scope === "here" ? select("Place", d.pathMode ? OTHER : d.place, placeItems, "draftPlace", "place", "Choose a place…") : ""}
        </div>
        ${d.scope === "here" && d.pathMode ? html`<input type="text" class="input mono" placeholder="~/repos/project" aria-label="Folder path" data-input="draft:path"${attrs({ value: d.path })}>` : ""}
      </div>
      <label class="field">
        <span class="field-label">Memory <span class="hint">Markdown</span></span>
        <textarea class="input mono body" spellcheck="false" placeholder="${"The fact itself.\n\n**Why:** …\n\n**How to apply:** …"}" data-input="draft:body">${d.body}</textarea>
      </label>
    </div>
    <div class="form-bar">
      <span class="form-error" role="alert">${app.formError}</span>
      <button type="button" class="btn" data-act="cancelEdit">Cancel</button>
      <button type="submit" class="btn primary" title="⌘S"${attrs({ disabled: app.saving })}>${isNew ? "Add memory" : "Save"}</button>
    </div>
  </form>`;
}

export const memoryPanel = () => (app.mode !== "view" && app.draft ? form() : app.open ? detail(app.open) : "");
export { OTHER };
