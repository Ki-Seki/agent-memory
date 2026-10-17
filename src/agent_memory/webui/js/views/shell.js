// A narrow rail (a top bar on phones), a compact list, and the open memory beside it.
// Below 1024px the list and the memory take turns; the logo always leads back to the memories.
import { attrs, cx, html } from "../h.js";
import { icon } from "../icons.js";
import { plural } from "../format.js";
import { app } from "../store.js";
import { insightsPage } from "./insights.js";
import { listPane } from "./list.js";
import { memoryPanel } from "./memory.js";
import { selectionBar, toasts } from "./overlays.js";
import { railProfile } from "./profiles.js";
import { settingsPage } from "./settings.js";

/** The mark: a lowercase m for mem, its last stroke ending in a stored point. */
export const mark = (size) => html`<svg class="mark" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true">
  <rect width="24" height="24" rx="7" fill="#5b5bd6"/>
  <path d="M6.5 17v-5.75a2.75 2.75 0 0 1 5.5 0V17M12 11.25a2.75 2.75 0 0 1 5.5 0V14" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="17.5" cy="17.2" r="1.6" fill="#fff"/></svg>`;

export const unpushed = () =>
  app.unpushed
    ? html`<button type="button" class="unpushed" title="Commits a hook or this page made but has not pushed yet" data-act="go" data-arg="settings"><i class="dot warn"></i>${plural(app.unpushed, "change")} not pushed</button>`
    : "";

const railButton = (page, label, name) => html`
  <button type="button" class="rail-btn"${attrs({ "aria-label": label, "data-tip": label, "data-tip-side": "right", "aria-current": app.page === page ? "page" : null, "data-act": "go", "data-arg": page })}>
    ${icon(name)}${page === "settings" && app.update?.available ? html`<i class="badge" aria-hidden="true"></i>` : ""}
  </button>`;

function rail() {
  const settings = app.update?.available ? `Settings · version ${app.update.latest} is out` : "Settings";
  return html`<nav class="rail">
    <button type="button" class="brand-btn" aria-label="Memories" data-tip="Memories" data-tip-side="right"${attrs({ "aria-current": app.page === "memories" ? "page" : null })} data-act="home">
      <span class="brand phone">${mark(28)}agent-memory</span><span class="brand desk">${mark(32)}</span>
    </button>
    ${railButton("insights", "Insights", "chart-column")}
    <div class="spacer"></div>
    ${railProfile(railButton("settings", settings, "settings-2"))}
  </nav>`;
}

function memories() {
  const width = app.listWidth ? `--list-w:${app.listWidth}px` : null;
  return html`<div${attrs({ class: cx("mem", app.reading && "reading"), style: width })}>
    ${listPane()}
    <section class="read-pane" data-key="read-pane">
      <div class="read-inner">
        ${app.reading ? html`<button type="button" class="back" data-act="close">${icon("arrow-left")}All memories</button>` : ""}
        ${app.mode !== "view" || app.open ? memoryPanel() : html`<p class="empty-read">Pick a memory to read it here.</p>`}
      </div>
    </section>
  </div>`;
}

function page() {
  const title = { insights: "Insights", settings: "Settings" }[app.page];
  return html`<section class="page" data-key="page-${app.page}">
    <header class="page-head"><h1>${title}</h1>${unpushed()}</header>
    <div class="page-body">${app.page === "insights" ? insightsPage() : settingsPage()}</div>
  </section>`;
}

export function view() {
  if (app.bootError) return html`<div class="boot">${app.bootError}</div>`;
  if (!app.data) return html`<div class="boot">Loading memories…</div>`;
  const bar = app.demo
    ? html`<div class="demo-bar" data-key="demo-bar"><span><b>Live demo</b> with made-up memories; changes stay in this tab.</span><a href="../">About agent-memory</a><a href="../#start">Install</a></div>`
    : "";
  return html`${bar}<div class="shell">${rail()}${app.page === "memories" ? memories() : page()}</div>${selectionBar()}${toasts()}`;
}
