// Settings: the open profile as a hero (its picture, name, where it lives and one sync state, with the other
// profiles in its foot), then a few quiet rows of preferences, and the installation's health as one line.
import { avatar, glow } from "../avatar.js";
import { since } from "../format.js";
import { attrs, cx, html } from "../h.js";
import { icon } from "../icons.js";
import { app } from "../store.js";
import { active, dock, newProfile, shown } from "./profiles.js";
import { segmented, toggle } from "./ui.js";

const copyCode = (text) => html`<button type="button" class="code-copy" title="Copy" data-act="copy" data-arg="${text}">${text}${icon("copy")}</button>`;
const spin = (on) => icon("refresh-cw", on ? "spin" : "");

// ---------------------------------------------------------------- the hero

function where(s) {
  const st = app.settings;
  const folder = s?.dataDir ?? app.data?.dataDir ?? "";
  const remote = s?.remote
    ? html`<span class="hero-meta-item">${icon("cloud")}<span class="v" title="${s.remoteUrl || s.remote}">${s.remote}</span><button type="button" class="hero-link" data-act="remoteEdit">Change</button></span>`
    : html`<span class="hero-meta-item">${icon("cloud")}<span class="k">No remote</span><button type="button" class="hero-link" data-act="remoteEdit">Add</button></span>`;
  return html`<div class="hero-meta">
    <button type="button" class="hero-meta-item" title="Copy the path" data-act="copy" data-arg="${folder}">${icon("folder")}<span class="v">${folder}</span>${icon("copy", "copy-hint")}</button>
    ${st.remoteEdit ? "" : remote}
  </div>`;
}

function remoteEdit(s) {
  const st = app.settings;
  return html`<div class="remote-edit">
    <label for="remote-url">${s?.remote ? "Remote" : "Connect a remote"}</label>
    <input id="remote-url" class="input mono" placeholder="git@github.com:you/agent-memory-data.git" autocomplete="off" spellcheck="false" data-input="remoteDraft"${attrs({ value: st.remoteDraft, disabled: st.remoteBusy })}>
    <div class="remote-edit-row">
      <button type="button" class="btn primary" data-act="remoteSave"${attrs({ disabled: st.remoteBusy || !st.remoteDraft.trim() })}>${st.remoteBusy ? html`${spin(true)}Connecting…` : s?.remote ? "Save" : "Connect"}</button>
      <button type="button" class="btn ghost" data-act="remoteCancel"${attrs({ disabled: st.remoteBusy })}>Cancel</button>
      ${s?.remote ? html`<span class="grow"></span><button type="button" class="btn ghost bad-text" data-act="remoteDisconnect"${attrs({ disabled: st.remoteBusy })}>Disconnect</button>` : ""}
    </div>
  </div>`;
}

function syncPill(s) {
  const changed = s?.lastCommit ? html`<span class="wide-only">changed </span>${since(s.lastCommit)}` : "no changes yet";
  if (!s?.remote) return html`<div class="sync-pill solo" role="status"><span class="sync-state"><i class="dot off"></i><span><b>On this machine only</b> · ${changed}</span></span></div>`;
  const state = app.unpushed
    ? html`<span class="sync-state"><i class="dot warn"></i><b>${app.unpushed === 1 ? "1 change" : `${app.unpushed} changes`} not pushed</b></span>`
    : html`<span class="sync-state"><i class="dot ok"></i><span><b>Synced</b> · ${changed}</span></span>`;
  return html`<div class="sync-pill" role="status">${state}<span class="sync-sep"></span>
    <button type="button" class="sync-btn" data-act="syncNow"${attrs({ disabled: app.settings.syncing })}>${spin(app.settings.syncing)}Sync now</button></div>`;
}

function hero() {
  const s = app.settings.s, st = app.settings, p = active();
  const name = p?.name ?? s?.name ?? "agent-memory";
  const count = `${app.M.length} ${app.M.length === 1 ? "memory" : "memories"}`;
  const role = !p ? "" : app.profiles.demo ? "The profile the page shows" : "Sessions use this profile";
  const note = st.remoteNote ? html`<p${attrs({ class: cx("hero-note", !st.remoteNote.ok && "bad"), role: "status" })}>${st.remoteNote.text}</p>` : "";
  return html`<section class="hero" data-key="hero" aria-label="${p ? "The open profile" : "The data repository"}">
    <div class="hero-glow" aria-hidden="true">${glow(name)}</div>
    <div class="hero-main">
      ${avatar(name, "hero-pic")}
      <h2 class="hero-name">${name}</h2>
      <p class="hero-sub">${count}${role ? html`<span class="sep">·</span>${role}` : ""}</p>
      ${where(s)}
      ${st.remoteEdit ? remoteEdit(s) : ""}
      ${note}
      ${syncPill(s)}
    </div>
    ${shown().length ? (app.pform ? newProfile() : dock()) : ""}
  </section>`;
}

// ---------------------------------------------------------------- the quiet rows

const pref = (label, sub, control, cls = "") => html`<div${attrs({ class: cx("pref", cls) })}>
  <div class="pref-text"><span class="pref-label">${label}</span>${sub ? html`<span class="pref-sub">${sub}</span>` : ""}</div>
  <div class="pref-ctl">${control}</div>
</div>`;

function prefs() {
  const s = app.settings.s, st = app.settings, u = app.update;
  const words = s?.keywordStopwords ?? [];
  const tags = html`${words.map((w) => html`<span class="tag" data-key="tag-${w}">${w}<button type="button"${attrs({ "aria-label": `Remove ${w}`, "data-act": "removeWord", "data-arg": w })}>${icon("x", "", 2.4)}</button></span>`)}
    <label class="tag-add">${icon("plus")}<input id="add-word" placeholder="Add a word" aria-label="Add a word that is never a keyword" data-input="word"${attrs({ value: st.word })}></label>`;
  // searching by meaning only needs a row when something is to be done about it
  const meaning = !s ? "" : !s.model.ready
    ? pref("Search by meaning", `Off · the model is ${s.model.size}`, copyCode(s.model.fetch))
    : !s.semantic ? pref("Search by meaning", "Restart mem ui to turn it on", "") : "";
  let update;
  if (u?.available && u.oneClick) {
    update = html`<button type="button" class="btn primary" data-act="runUpdate"${attrs({ disabled: !!app.updating })}>
      ${app.updating ? html`${spin(true)}${app.updating === "restarting" ? "Restarting…" : "Updating…"}` : html`${icon("circle-arrow-up")}Update to ${u.latest}`}</button>`;
  } else if (u?.available) update = copyCode(u.command);
  else update = html`<button type="button" class="btn ghost" data-act="checkNow"${attrs({ disabled: st.lookingUp })}>${spin(st.lookingUp)}Check now</button>`;
  const said = !u ? "Checking for updates…" : u.available ? `${u.latest} is out` : u.latest ? "Up to date" : u.auto ? "Could not reach PyPI" : "";
  const theme = segmented("Theme", app.theme, [{ value: "system", label: "System" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }], "setTheme");
  return html`<section class="prefs" aria-label="Preferences">
    ${pref("Excluded words", "Never become keyword chips or filters", tags, "wrap")}
    ${meaning}
    ${pref("Theme", "", theme)}
    ${pref(`agent-memory ${u?.current ?? s?.version ?? ""}`, said, update)}
    ${st.failed ? html`<div class="callout bad"><div><div class="callout-title">${st.failed.error}</div>${st.failed.log ? html`<pre>${st.failed.log}</pre>` : ""}</div></div>` : ""}
    ${pref("Check for updates daily", "PyPI is sent only the package name", toggle(u?.auto ?? true, "Check for updates daily", "autoUpdate"))}
  </section>`;
}

// ---------------------------------------------------------------- the installation, one line

function doctor() {
  const { checks, checking, healthOpen } = app.settings;
  const failing = (checks ?? []).filter((c) => !c.ok);
  const summary = !checks ? "Checking the installation…" : failing.length ? `${failing.length} of ${checks.length} checks failing` : `All ${checks.length} checks pass`;
  const list = (items) => html`<ul>${items.map((c) => html`<li${attrs({ class: c.ok ? null : "bad" })}>${icon(c.ok ? "check" : "triangle-alert")}<span>${c.text}</span></li>`)}</ul>`;
  return html`<section class="doctor" aria-label="Installation">
    <div class="doctor-line">
      <button type="button"${attrs({ class: cx("doctor-sum", failing.length && "warn"), "data-act": "toggleHealth", "aria-expanded": String(!!healthOpen), disabled: !checks?.length })}>
        <i${attrs({ class: cx("dot", checks ? (failing.length ? "warn" : "ok") : "off") })}></i>${summary}${checks?.length ? icon("chevron-down", healthOpen ? "chev turned" : "chev") : ""}
      </button>
      <span class="sep">·</span>
      <button type="button" class="doctor-again" data-act="runChecks"${attrs({ disabled: checking })}>${spin(checking)}Run again</button>
    </div>
    ${healthOpen && checks ? html`<div class="checks"><p class="checks-note">The same checks as <code>mem doctor</code>.</p>${list(checks)}</div>`
      : failing.length ? html`<div class="checks">${list(failing)}</div>` : ""}
  </section>`;
}

export function settingsPage() {
  return html`<div class="settings">${hero()}${prefs()}${doctor()}</div>`;
}
