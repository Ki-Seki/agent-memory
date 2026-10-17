// Profiles: separate memory repositories, each its own folder and remote. Settings opens on the active one, with
// the others in its foot; the rail's last button is the active profile's picture, which leads there. A profile's name is picked for it when it is made, and its picture is
// drawn from the name.
import { avatar } from "../avatar.js";
import { attrs, html } from "../h.js";
import { icon } from "../icons.js";
import { app } from "../store.js";

/** Profiles to list, or none when the page cannot change them (AGENT_MEMORY_DATA picks the folder). */
export const shown = () => (app.profiles && !app.profiles.locked ? app.profiles.profiles : []);
export const active = () => shown().find((p) => p.active) ?? null;

// ---------------------------------------------------------------- the foot of Settings' hero

/** Every profile, in the order they were made so none moves when another is picked (the open one marked), New
 *  profile, and removing the open one. */
export function dock() {
  const list = shown();
  return html`<div class="dock" role="group" aria-label="Profiles">
    <span class="dock-label">Profiles</span>
    ${list.map((p) => html`<button type="button"${attrs({ class: "pchip", "data-key": `pchip-${p.id}`, "data-act": "useProfile", "data-arg": p.id, "aria-pressed": String(p.active), disabled: !!app.switching && !p.active, title: p.active ? `${p.name} is open` : `Switch to ${p.name}` })}>
      ${avatar(p.name)}${p.name}<span class="n">${p.memories}</span></button>`)}
    <button type="button" class="pchip add" data-act="profileNew"><span class="plus">${icon("plus")}</span>New profile</button>
    <span class="grow"></span>
    ${list.length > 1 ? html`<button type="button" class="dock-remove" data-act="profileRemove">Remove profile</button>` : ""}
  </div>`;
}

/** In place of the foot: the name and picture the new profile will have, its folder and an optional remote. */
export function newProfile() {
  const f = app.pform;
  return html`<form class="pform" data-profile-form aria-label="New profile">
    <div class="pform-top">${avatar(f.name)}<div><div class="pform-name">${f.name}</div><div class="pform-note">Name and picture are picked for you</div></div></div>
    <div class="pform-fields">
      <label class="pfield"><span>Folder</span><input id="pf-folder" class="input mono" placeholder="~/agent-memory-work" autocomplete="off" spellcheck="false" data-input="pform:folder"${attrs({ value: f.folder, disabled: f.busy })}></label>
      <label class="pfield"><span>Remote <i>(optional)</i></span><input class="input mono" placeholder="git@github.com:you/agent-memory-work.git" autocomplete="off" spellcheck="false" data-input="pform:remote"${attrs({ value: f.remote, disabled: f.busy })}></label>
    </div>
    ${f.error ? html`<p class="pform-error" role="alert">${f.error}</p>` : ""}
    <div class="pform-actions">
      <button type="submit" class="btn primary"${attrs({ disabled: f.busy || !f.folder.trim() })}>${f.busy ? html`${icon("refresh-cw", "spin")}Creating…` : "Create and switch"}</button>
      <button type="button" class="btn ghost" data-act="profileCancel"${attrs({ disabled: f.busy })}>Cancel</button>
    </div>
  </form>`;
}

// ---------------------------------------------------------------- the rail

/** The rail's last button: the active profile's picture, which opens Settings, where profiles are switched. Without
 *  profiles (AGENT_MEMORY_DATA picks the folder, or an older server) the rail keeps `fallback`, a Settings button. */
export function railProfile(fallback) {
  const now = active();
  if (!now) return fallback;
  const update = app.update?.available ? app.update.latest : "";
  const label = `${now.name} · Settings${update ? ` · version ${update} is out` : ""}`;
  return html`<button type="button" class="rail-profile"${attrs({ "aria-label": label, "data-tip": label, "data-tip-side": "right", "aria-current": app.page === "settings" ? "page" : null, "data-act": "go", "data-arg": "settings" })}>${avatar(now.name)}${update ? html`<i class="badge" aria-hidden="true"></i>` : ""}</button>`;
}
