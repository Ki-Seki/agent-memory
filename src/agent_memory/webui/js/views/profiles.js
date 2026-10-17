// Profiles: separate memory repositories, each its own folder and remote. Settings lists them above the
// repository card, which shows the active one; the rail's last button is the active profile's picture, with
// Settings and a quick switch behind it. A profile's name is picked for it when it is made, and its picture is
// drawn from the name.
import { avatar } from "../avatar.js";
import { plural } from "../format.js";
import { attrs, cx, html } from "../h.js";
import { icon } from "../icons.js";
import { app } from "../store.js";
import { menu } from "./ui.js";

/** Profiles to list, or none when the page cannot change them (AGENT_MEMORY_DATA picks the folder). */
export const shown = () => (app.profiles && !app.profiles.locked ? app.profiles.profiles : []);
export const active = () => shown().find((p) => p.active) ?? null;

// ---------------------------------------------------------------- the strip above the repository card

export function profileStrip() {
  const list = shown();
  if (!list.length) return "";
  const adding = !!app.pform, now = active();
  return html`<div class="profiles">
    <div class="ptabs" role="radiogroup" aria-label="Profiles">
      ${list.map((p) => html`<button type="button" role="radio"${attrs({ class: "ptab", "data-key": `ptab-${p.id}`, "aria-checked": String(p.active && !adding), "data-act": "useProfile", "data-arg": p.id, disabled: !!app.switching, title: p.active ? `${p.name} · ${p.dataDir}` : `Switch to ${p.name}` })}>
        ${avatar(p.name)}<span class="ptab-name">${p.name}</span><span class="ptab-count">${p.memories}</span>
      </button>`)}
      <button type="button"${attrs({ class: cx("ptab", "add"), "aria-pressed": String(adding), "data-act": "profileNew" })}>${icon("plus")}New profile</button>
    </div>
    ${list.length > 1 && now && !adding ? html`<p class="profiles-help">${app.profiles.demo
      ? html`Set up for real, new Claude Code and Codex sessions would use <b>${now.name}</b>; the demo is not connected to them.`
      : html`New Claude Code and Codex sessions use <b>${now.name}</b>. Sessions already running keep the profile they started in.`}</p>` : ""}
  </div>`;
}

// ---------------------------------------------------------------- a new profile

/** The card that takes the repository card's place while a profile is being added. */
export function profileNewCard() {
  const f = app.pform;
  return html`<section class="repo-card">
    <form class="pform" data-profile-form>
      <div class="pform-top">
        ${avatar(f.name, "lg")}
        <div class="grow">
          <h2>${f.name}</h2>
          <p class="pform-sub">A new profile: a separate set of memories in its own repository. Its name and picture are picked for it.</p>
        </div>
      </div>
      <label class="pfield"><span class="field-label">Folder</span>
        <input id="pf-folder" class="input mono" placeholder="~/agent-memory-work" autocomplete="off" spellcheck="false" data-input="pform:folder"${attrs({ value: f.folder, disabled: f.busy })}>
        <span class="field-help">A new or empty folder becomes a memory repository. One that already is one is used as it is.</span>
      </label>
      <label class="pfield"><span class="field-label">Remote <span class="faint">(optional)</span></span>
        <input class="input mono" placeholder="git@github.com:you/agent-memory-work.git" autocomplete="off" spellcheck="false" data-input="pform:remote"${attrs({ value: f.remote, disabled: f.busy })}>
        <span class="field-help">Leave it empty to keep these memories on this machine. With a new folder, a remote that already has memories is cloned; an empty one gets the new repository pushed to it.</span>
      </label>
      ${f.error ? html`<p class="pform-error" role="alert">${f.error}</p>` : ""}
      <div class="pform-actions">
        <button type="submit" class="btn primary sm"${attrs({ disabled: f.busy || !f.folder.trim() })}>${f.busy ? html`${icon("refresh-cw", "spin")}Creating…` : "Create and switch"}</button>
        <button type="button" class="btn ghost sm" data-act="profileCancel"${attrs({ disabled: f.busy })}>Cancel</button>
      </div>
    </form>
  </section>`;
}

// ---------------------------------------------------------------- the rail

/** The rail's last button: the active profile's picture, opening a menu with Settings and the profiles. Without
 *  profiles (AGENT_MEMORY_DATA picks the folder, or an older server) the rail keeps `fallback`, a Settings button. */
export function railProfile(fallback) {
  const list = shown(), now = active();
  if (!now) return fallback;
  const update = app.update?.available ? app.update.latest : "";
  const label = `${now.name} · Settings${update ? ` · version ${update} is out` : ""}`;
  return html`<button type="button" class="rail-profile" popovertarget="menu-profiles"${attrs({ "aria-label": label, "data-tip": label, "data-tip-side": "right", "aria-current": app.page === "settings" ? "page" : null })}>${avatar(now.name)}${update ? html`<i class="badge" aria-hidden="true"></i>` : ""}</button>
    ${menu("menu-profiles", html`<div class="menu-list" role="menu">
      <button type="button" role="menuitem" class="menu-item" data-act="openSettings">${icon("settings-2")}<span class="grow">Settings</span>${update ? html`<span class="count accent">${update} is out</span>` : ""}</button>
      <div class="menu-sep" role="separator"></div>
      <div class="menu-note pad">${app.profiles.demo ? "Profile the page shows" : "Profile new sessions use"}</div>
      ${list.map((p) => html`<button type="button" role="menuitemradio"${attrs({ class: "menu-item tall", "aria-checked": String(p.active), "data-act": "useProfile", "data-arg": p.id })}>
        ${avatar(p.name, "sm")}<span class="grow truncate">${p.name}</span><span class="count">${plural(p.memories, "memory", "memories")}</span>${p.active ? icon("check", "accent") : html`<span class="tick-space"></span>`}
      </button>`)}
      <button type="button" role="menuitem" class="menu-item" data-act="profileNewFromMenu">${icon("plus")}<span class="grow">New profile</span></button>
    </div>`, "", "side")}`;
}
