// Settings: the profiles and the data repository first (where it is, its remote, sync), then search, general
// settings, and health as one line that opens when asked or when something fails.
import { plural, since } from "../format.js";
import { attrs, cx, html } from "../h.js";
import { icon } from "../icons.js";
import { app } from "../store.js";
import { avatar } from "../avatar.js";
import { active, profileNewCard, profileStrip, shown } from "./profiles.js";
import { segmented, status, toggle } from "./ui.js";

/** A setting: its name and help on the left, the control on the right. */
const row = (label, help, control) => html`<div class="setting">
  <div><div class="setting-name">${label}</div>${help ? html`<div class="setting-help">${help}</div>` : ""}</div>
  <div class="setting-control">${control}</div>
</div>`;

const copyCode = (text) => html`<button type="button" class="code-copy" title="Copy" data-act="copy" data-arg="${text}"><span>${text}</span>${icon("copy")}</button>`;

function syncState(s) {
  if (!s?.remote) return html`<span class="pill">${icon("laptop")}On this machine only</span>`;
  if (app.unpushed) return html`<span class="pill warn">${plural(app.unpushed, "change")} not pushed</span>`;
  return html`<span class="pill ok">${icon("check", "", 2.5)}Synced</span>`;
}

function remote(s) {
  const st = app.settings;
  const note = st.remoteNote ? html`<p${attrs({ class: cx("remote-note", !st.remoteNote.ok && "bad") })} role="status">${st.remoteNote.text}</p>` : "";
  if (st.remoteEdit) {
    return html`<div class="remote-row editing">
      <span class="remote-icon">${icon("cloud")}</span>
      <div class="grow">
        <label class="remote-label" for="remote-url">${s?.remote ? "Change the remote" : "Connect a remote"}</label>
        <div class="remote-form">
          <input id="remote-url" class="input mono" placeholder="git@github.com:you/agent-memory-data.git" autocomplete="off" spellcheck="false" data-input="remoteDraft"${attrs({ value: st.remoteDraft, disabled: st.remoteBusy })}>
          <button type="button" class="btn primary sm" data-act="remoteSave"${attrs({ disabled: st.remoteBusy || !st.remoteDraft.trim() })}>${st.remoteBusy ? html`${icon("refresh-cw", "spin")}Connecting…` : s?.remote ? "Save" : "Connect"}</button>
          <button type="button" class="btn ghost sm" data-act="remoteCancel"${attrs({ disabled: st.remoteBusy })}>Cancel</button>
        </div>
        <p class="remote-help">An empty private repository works: this one is pushed to it. One that other machines already push to is pulled from first.</p>
        ${note}
      </div>
    </div>`;
  }
  if (!s?.remote) {
    return html`<div class="remote-row">
      <span class="remote-icon">${icon("cloud")}</span>
      <div class="grow"><div class="remote-title">No remote</div>
        <p class="remote-help">Every change is still committed here. Add a private remote to keep your other machines in sync.</p>${note}</div>
      <button type="button" class="btn sm" data-act="remoteEdit">${icon("plus")}Add remote</button>
    </div>`;
  }
  return html`<div class="remote-row">
    <span class="remote-icon on">${icon("cloud")}</span>
    <div class="grow"><div class="remote-title">Remote</div><code class="remote-url">${s.remoteUrl || s.remote}</code>${note}</div>
    <div class="inline-gap">
      <button type="button" class="btn ghost sm" data-act="remoteEdit">Change</button>
      <button type="button" class="btn ghost sm bad-text" data-act="remoteDisconnect">Disconnect</button>
    </div>
  </div>`;
}

function repository() {
  if (app.pform) return profileNewCard();
  const s = app.settings.s, p = active();
  const facts = [
    ["Memories", String(app.M.length)],
    ["Last change", s?.lastCommit ? since(s.lastCommit) : "never"],
  ];
  const head = html`<header class="repo-card-head">
      ${p ? avatar(p.name, "lg") : html`<span class="repo-mark">${icon("git-branch")}</span>`}
      <div class="grow">
        <h2 class="repo-title">${p?.name ?? s?.name ?? "Data repository"}${p && shown().length > 1 ? html`<button type="button" class="btn ghost icon" aria-label="Remove this profile" data-tip="Remove this profile" data-act="profileRemove">${icon("trash")}</button>` : ""}</h2>
        <button type="button" class="path-copy" title="Copy the path" data-act="copy" data-arg="${s?.dataDir ?? ""}">${s?.dataDir ?? app.data?.dataDir}${icon("copy")}</button>
      </div>
      ${syncState(s)}
      ${s?.remote ? html`<button type="button" class="btn sm" data-act="syncNow"${attrs({ disabled: app.settings.syncing })}>${icon("refresh-cw", app.settings.syncing ? "spin" : "")}Sync now</button>` : ""}
    </header>`;
  return html`<section class="repo-card" data-key="repo-card">
    ${head}
    <dl class="repo-facts">${facts.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>
    ${remote(s)}
  </section>`;
}

function search() {
  const s = app.settings.s;
  const words = s?.keywordStopwords ?? [];
  const model = html`<div class="model-state">${s?.model.ready
    ? status("ok", `Ready${s.semantic ? "" : " (restart mem ui to use it)"}`)
    : html`${status("off", "Not downloaded")}${s ? copyCode(s.model.fetch) : ""}`}</div>`;
  return html`<section class="group"><h2>Search</h2>
    ${row("Search by meaning", `${s?.model.name ?? "A local embedding model"}, on the CPU (${s?.model.size ?? "about 625 MB"}), across Chinese and English.`, model)}
    ${row("Never use as keywords", "Words such as your own name, kept out of keyword chips and filters.", html`<div class="tags-input">
      ${words.map((w) => html`<span class="tag" data-key="tag-${w}">${w}<button type="button"${attrs({ "aria-label": `Remove ${w}`, "data-act": "removeWord", "data-arg": w })}>${icon("x")}</button></span>`)}
      <input id="add-word" placeholder="Add a word" data-input="word"${attrs({ value: app.settings.word })}>
    </div>`)}
  </section>`;
}

function general() {
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
  const theme = segmented("Theme", app.theme, [{ value: "system", label: "System" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }], "setTheme");
  return html`<section class="group"><h2>General</h2>
    ${row("Theme", "Follow the system, or pick one.", theme)}
    ${row(`agent-memory ${u?.current ?? s?.version ?? ""}`, help, control)}
    ${st.failed ? html`<div class="callout bad"><div><div class="callout-title">${st.failed.error}</div>${st.failed.log ? html`<pre>${st.failed.log}</pre>` : ""}</div></div>` : ""}
    ${row("Check for updates", "Once a day this page asks PyPI for the latest version; only the package name is sent.", toggle(u?.auto ?? true, "Check for updates automatically", "autoUpdate"))}
  </section>`;
}

function health() {
  const { checks, checking, healthOpen } = app.settings;
  const failing = (checks ?? []).filter((c) => !c.ok);
  const shown = healthOpen ? checks ?? [] : failing;
  const summary = !checks ? "Checking the installation…"
    : failing.length ? `${failing.length} of ${checks.length} checks failing` : `All ${checks.length} checks pass`;
  return html`<section class="group health">
    <div class="health-summary">
      <span${attrs({ class: cx("health-icon", checks && (failing.length ? "warn" : "ok")) })}>${icon(failing.length ? "triangle-alert" : "check", "", 2.5)}</span>
      <div class="grow"><div class="setting-name">${summary}</div><div class="setting-help">The same checks as <code>mem doctor</code>.</div></div>
      ${checks?.length ? html`<button type="button" class="btn ghost sm" data-act="toggleHealth">${healthOpen ? "Hide" : "Show all"}</button>` : ""}
      <button type="button" class="btn sm" data-act="runChecks"${attrs({ disabled: checking })}>${icon("refresh-cw", checking ? "spin" : "")}Run again</button>
    </div>
    ${shown.length ? html`<ul class="checks">${shown.map((c) => html`<li>${icon(c.ok ? "check" : "triangle-alert", c.ok ? "ok-text" : "warn-text")}<span>${c.text}</span></li>`)}</ul>` : ""}
  </section>`;
}

export function settingsPage() {
  return html`<div class="settings"><div class="repo-stack">${profileStrip()}${repository()}</div>${search()}${general()}${health()}</div>`;
}
