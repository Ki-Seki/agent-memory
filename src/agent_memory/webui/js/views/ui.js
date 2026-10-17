// Small pieces the views share. Clicks reach the store through data-act (see main.js), so markup stays markup.
import { attrs, html } from "../h.js";
import { icon } from "../icons.js";

export const typeDot = (type, label = false) =>
  label ? html`<span class="type-label"><i class="dot t-${type}"></i>${type}</span>` : html`<i class="dot t-${type}" aria-hidden="true"></i>`;

export const kbd = (k) => html`<kbd class="kbd">${k}</kbd>`;

/** A button that shows only an icon, named by its tooltip. */
export const iconButton = (name, label, act, arg, side = "bottom") =>
  html`<button type="button" class="btn ghost icon"${attrs({ "aria-label": label, "data-tip": label, "data-tip-side": side, "data-act": act, "data-arg": arg })}>${icon(name)}</button>`;

/** A row of options where one is on; `lead` may draw a dot or icon before each label. */
export const segmented = (label, value, options, act, lead) => html`
  <div class="seg" role="radiogroup" aria-label="${label}">
    ${options.map((o) => html`<button type="button" role="radio"${attrs({ "aria-checked": String(o.value === value), "data-act": act, "data-arg": o.value })}>${lead ? lead(o.value) : ""}${o.label}</button>`)}
  </div>`;

export const checkbox = (on, label, act, arg) =>
  html`<button type="button" role="checkbox" class="check"${attrs({ "aria-checked": String(on), "aria-label": label, "data-act": act, "data-arg": arg })}>${on ? icon("check", "", 3) : ""}</button>`;

export const toggle = (on, label, act) =>
  html`<button type="button" role="switch" class="switch"${attrs({ "aria-checked": String(on), "aria-label": label, "data-act": act })}><span></span></button>`;

/** A native select; `act` gets the chosen value. */
export const select = (label, value, items, act, cls = "", placeholder = "") => html`
  <span class="select ${cls}">
    <select${attrs({ "aria-label": label, "data-change": act })}>
      ${placeholder && !items.some((i) => i.value === value) ? html`<option value="" disabled selected>${placeholder}</option>` : ""}
      ${items.map((i) => html`<option${attrs({ value: i.value, selected: i.value === value })}>${i.label}</option>`)}
    </select>${icon("chevron-down")}
  </span>`;

/** A menu that opens under its trigger (the trigger names it with popovertarget). */
export const menu = (id, content, cls = "", align = "start") =>
  html`<div${attrs({ id, popover: "", class: `menu ${cls}`, "data-align": align, "data-live": "style" })}>${content}</div>`;

/** A note that something is good, waiting or wrong. */
export const status = (tone, text) => html`<span class="status"><i class="dot ${tone}"></i>${text}</span>`;
