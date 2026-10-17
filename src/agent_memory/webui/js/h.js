// Rendering without a framework: views return html`...` strings, and morph() patches the page to match,
// keeping elements that stay (so focus, scroll positions, open menus and typed text survive a render).

class Html {
  constructor(s) { this.s = s; }
  toString() { return this.s; }
}

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
const part = (v) => (v == null || v === false ? "" : v instanceof Html ? v.s : Array.isArray(v) ? v.map(part).join("") : esc(v));

/** A template whose values are escaped, unless they are html already (or lists of it). */
export function html(strings, ...values) {
  let s = strings[0];
  values.forEach((v, i) => { s += part(v) + strings[i + 1]; });
  return new Html(s);
}
export const raw = (s) => new Html(s);
export const cx = (...names) => names.filter(Boolean).join(" ");
/** Attributes from an object; null, undefined and false leave an attribute out, true writes it bare. */
export const attrs = (o) =>
  raw(Object.entries(o).map(([k, v]) => (v == null || v === false ? "" : v === true ? ` ${k}` : ` ${k}="${esc(v)}"`)).join(""));

// ---------------------------------------------------------------- morph

const keyOf = (n) => (n.nodeType === 1 ? n.getAttribute("data-key") || n.id || null : null);
const same = (a, b) => a.nodeType === b.nodeType && a.nodeName === b.nodeName && (a.nodeName !== "INPUT" || a.type === b.type);

/** Make the children of `el` match `markup`. */
export function morph(el, markup) {
  const t = document.createElement("template");
  t.innerHTML = String(markup);
  children(el, t.content);
}

function children(parent, next) {
  const keyed = new Map();
  for (const n of parent.childNodes) { const k = keyOf(n); if (k) keyed.set(k, n); }
  let i = 0;
  for (const want of [...next.childNodes]) {
    const cur = parent.childNodes[i] ?? null;
    const k = keyOf(want);
    let have = k ? keyed.get(k) : cur && !keyOf(cur) && same(cur, want) ? cur : null;
    if (have && !same(have, want)) have = null;
    if (have) {
      if (have !== cur) parent.insertBefore(have, cur);
      patch(have, want);
    } else parent.insertBefore(want, cur);
    i++;
  }
  while (parent.childNodes.length > i) parent.lastChild.remove();
}

function patch(el, want) {
  if (el.nodeType !== 1) {
    if (el.nodeValue !== want.nodeValue) el.nodeValue = want.nodeValue;
    return;
  }
  const live = (want.getAttribute("data-live") || "").split(" ");  // attributes the page sets itself, such as a menu's position
  for (const { name } of [...el.attributes]) if (!want.hasAttribute(name) && !live.includes(name)) el.removeAttribute(name);
  for (const { name, value } of want.attributes) if (el.getAttribute(name) !== value) el.setAttribute(name, value);
  const tag = el.nodeName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
    // what the page holds wins over what the user sees only when they differ and the field is not being typed in
    if (tag === "SELECT") children(el, want);
    const value = tag === "TEXTAREA" ? want.textContent : want.getAttribute("value") ?? (tag === "SELECT" ? want.value : "");
    if (el.value !== value && (document.activeElement !== el || tag === "SELECT")) el.value = value;
    if (tag === "INPUT") el.checked = want.hasAttribute("checked");
    return;
  }
  if (el.hasAttribute("data-own")) return;  // an element whose content is managed elsewhere
  children(el, want);
}
