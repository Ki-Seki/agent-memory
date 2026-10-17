// Settings: theme, updates, the data repository and sync, keyword stopwords, the embedding model, health.
import { plural, since } from "../format.js";
import { attrs, html } from "../h.js";
import { icon } from "../icons.js";
import { app } from "../store.js";
import { segmented, status, toggle } from "./ui.js";

/** A setting: its name and help on the left, the control on the right; `below` puts a long value under the name. */
const row = (label, help, control, below = false) => html`<div class="${below ? "setting below" : "setting"}">
  <div><div class="setting-name">${label}</div>${help ? html`<div class="setting-help">${help}</div>` : ""}</div>
  <div class="setting-control">${control}</div>
</div>`;

const copyCode = (text) => html`<button type="button" class="code-copy" title="Copy" data-act="copy" data-arg="${text}"><span>${text}</span>${icon("copy")}</button>`;

function updates() {
  const u = app.update, st = app.settings, s = st.s;
  let control;
  if (u?.available && u.oneClick) {
    control = html`<button type="button" class="btn primary sm" data-act="runUpdate"${attrs({ disabled: !!app.updating })}>
      ${app.updating ? html`${icon("refresh-cw", "spin")}${app.updating === "restarting" ? "Restarting…" : "Updating…"}` : html`${icon("circle-arrow-up")}Update to ${u.latest}`}</button>`;
  } else if (u?.available) control = copyCode(u.command);
  else control = html`<button type="button" class="btn sm" data-act="checkNow"${attrs({ disabled: st.lookingUp })}>${icon("refresh-cw", st.lookingUp ? "spin" : "")}Check now</button>`;
  const help = !u ? "Checking for updates…"
    : u.available ? `Version ${u.latest} is out.${u.oneClick ? " Updating also refreshes the hooks and restarts this page." : u.method === "dev" ? " This is a working copy; in it, run:" : " Update with:"}`
    : u.latest ? `Up to date${u.checked ? `, checked ${since(u.checked)}` : ""}.` : u.auto ? "Could not reach PyPI to check." : "Automatic checks are off.";
  return html`<section class="group"><h2>Updates</h2>
    ${row(`agent-memory ${u?.current ?? s?.version ?? ""}`, help, control)}
    ${st.failed ? html`<div class="callout bad"><div><div class="callout-title">${st.failed.error}</div>${st.failed.log ? html`<pre>${st.failed.log}</pre>` : ""}</div></div>` : ""}
    ${row("Check automatically", "Once a day this page asks PyPI for the latest version; only the package name is sent.", toggle(u?.auto ?? true, "Check for updates automatically", "autoUpdate"))}
  </section>`;
}

function repository() {
  const s = app.settings.s;
  const sync = html`<div class="inline-gap">
    ${s?.remote ? (app.unpushed ? html`<span class="status warn-text"><i class="dot warn"></i>${plural(app.unpushed, "change")} not pushed</span>` : status("ok", "Up to date")) : ""}
    <button type="button" class="btn sm" data-act="syncNow"${attrs({ disabled: app.settings.syncing || !s?.remote })}>${icon("refresh-cw", app.settings.syncing ? "spin" : "")}Sync now</button>
  </div>`;
  return html`<section class="group"><h2>Data repository</h2>
    ${row("Location", "Every memory is one Markdown file in this git repository.", html`<code class="block-code">${s?.dataDir ?? app.data?.dataDir}</code>`, true)}
    ${row("Remote", null, s?.remote ? html`<code class="chip-code">${s.remote}</code>` : html`<span class="muted">None, so memories stay on this machine</span>`)}
    ${row("Sync", "Hooks commit and push after every turn; this pulls and pushes now.", sync)}
  </section>`;
}

function keywords() {
  const words = app.settings.s?.keywordStopwords ?? [];
  return html`<section class="group"><h2>Keywords</h2>
    ${row("Never use as keywords", "Words such as your own name, kept out of keyword chips and filters.", html`<div class="tags-input">
      ${words.map((w) => html`<span class="tag" data-key="tag-${w}">${w}<button type="button"${attrs({ "aria-label": `Remove ${w}`, "data-act": "removeWord", "data-arg": w })}>${icon("x")}</button></span>`)}
      <input id="add-word" placeholder="Add a word" data-input="word"${attrs({ value: app.settings.word })}>
    </div>`)}
  </section>`;
}

function model() {
  const s = app.settings.s;
  const control = html`<div class="model-state">${s?.model.ready
    ? status("ok", `Ready${s.semantic ? "" : " (restart mem ui to use it)"}`)
    : html`${status("off", "Not downloaded")}${s ? copyCode(s.model.fetch) : ""}`}</div>`;
  return html`<section class="group"><h2>Search by meaning</h2>
    ${row("Local model", `${s?.model.name ?? "Embedding model"}, on the CPU; ${s?.model.size ?? ""}. Finds memories close in meaning, across Chinese and English.`, control)}
  </section>`;
}

function health() {
  const { checks, checking } = app.settings;
  const failing = checks?.filter((c) => !c.ok).length ?? 0;
  return html`<section class="group">
    <div class="group-head"><h2>Health</h2>${checks ? html`<span class="${failing ? "warn-text small" : "muted small"}">${failing ? `${plural(failing, "check")} failing` : "All checks pass"}</span>` : ""}</div>
    <ul class="checks">${(checks ?? []).map((c) => html`<li>${icon(c.ok ? "check" : "triangle-alert", c.ok ? "ok-text" : "warn-text")}<span>${c.text}</span></li>`)}</ul>
    <div class="group-foot"><span class="muted small">The same checks as <code>mem doctor</code></span>
      <button type="button" class="btn sm" data-act="runChecks"${attrs({ disabled: checking })}>Run checks again</button></div>
  </section>`;
}

export function settingsPage() {
  const theme = segmented("Theme", app.theme, [{ value: "system", label: "System" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }], "setTheme");
  return html`<div class="settings">
    <section class="group"><h2>Appearance</h2>${row("Theme", "Follow the system, or pick one.", theme)}</section>
    ${updates()}${repository()}${keywords()}${model()}${health()}
  </div>`;
}
