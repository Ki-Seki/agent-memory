// What floats over the page: the bar for selected memories, toasts, and the two dialogs.
import { longDay } from "../format.js";
import { html } from "../h.js";
import { icon } from "../icons.js";
import { parse, renderBlocks } from "../markdown.js";
import { app } from "../store.js";
import { typeDot } from "./ui.js";

export function selectionBar() {
  if (!app.picked.size) return "";
  const shown = app.rows.map((m) => m.id);
  const rest = shown.filter((id) => !app.picked.has(id)).length;
  return html`<div class="selection" data-key="selection">
    <span class="selection-n">${app.picked.size} selected</span>
    ${rest ? html`<button type="button" data-act="pickAll">Select all ${shown.length}</button>` : ""}
    <button type="button" data-act="clearPicked">Clear</button>
    <button type="button" class="danger" data-act="removePicked">Delete</button>
  </div>`;
}

export function toasts() {
  return html`<div class="toasts" aria-live="polite" data-key="toasts">
    ${app.toasts.map((t) => html`<div class="${t.error ? "toast bad" : "toast"}" data-key="toast-${t.id}"><span>${t.text}</span>
      ${t.undo ? html`<button type="button" data-act="undoToast" data-arg="${t.id}">Undo</button>` : ""}</div>`)}
  </div>`;
}

export function confirmDialog() {
  const a = app.asking;
  if (!a) return "";
  return html`<h2 class="dialog-title">${a.title}</h2>
    ${a.body ? html`<p class="dialog-body">${a.body}</p>` : ""}
    <div class="dialog-actions">
      <button type="button" class="btn" data-act="answer" data-arg="no">Cancel</button>
      <button type="button" class="${a.danger ? "btn danger" : "btn primary"}" data-act="answer" data-arg="yes" autofocus>${a.action}</button>
    </div>`;
}

/** Two similar memories side by side, to keep one, open either, or delete one. */
export function compareDialog() {
  const pair = app.comparing;
  if (!pair) return "";
  const wiki = (name) => html`<span>[[${name}]]</span>`;
  return html`<div class="dialog-head"><h2 class="dialog-title">Compare two similar memories</h2>
      <span class="count">${Math.round(pair[2] * 100)}% alike</span>
      <button type="button" class="btn ghost icon" aria-label="Close" data-act="closeCompare">${icon("x")}</button></div>
    <div class="compare">${[pair[0], pair[1]].map((m) => html`<section>
      <h3>${m.description}</h3>
      <div class="compare-meta">${typeDot(m.type, true)}·<span>${m.scope === "global" ? "Everywhere" : m.place}</span>·<span>${longDay(m.created)}</span></div>
      <div class="md small">${renderBlocks(parse(m.body), wiki)}</div>
      <div class="compare-actions"><button type="button" class="btn sm" data-act="open" data-arg="${m.id}">Open</button>
        <button type="button" class="btn sm ghost bad-text" data-act="removeCompared" data-arg="${m.id}">Delete this one</button></div>
    </section>`)}</div>`;
}
