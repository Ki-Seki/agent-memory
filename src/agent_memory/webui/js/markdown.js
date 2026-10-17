// The Markdown memories use, parsed to a small tree and rendered from it; no raw HTML from a memory
// ever reaches the page.
import { html } from "./h.js";

const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\[\[[^\]]+\]\])|(\[[^\]]+\]\((?:https?:\/\/)[^)\s]+\))|(\*[^*\s][^*]*\*)|(https?:\/\/[^\s<>()]+)/g;

export function inline(text) {
  const out = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) out.push({ k: "text", v: text.slice(last, m.index) });
    const s = m[0];
    if (m[1]) out.push({ k: "code", v: s.slice(1, -1) });
    else if (m[2]) out.push({ k: "strong", c: inline(s.slice(2, -2)) });
    else if (m[3]) out.push({ k: "wiki", name: s.slice(2, -2) });
    else if (m[4]) { const mm = s.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/); out.push({ k: "link", text: mm[1], href: mm[2] }); }
    else if (m[5]) out.push({ k: "em", c: inline(s.slice(1, -1)) });
    else out.push({ k: "link", text: s, href: s });
    last = m.index + s.length;
  }
  if (last < text.length) out.push({ k: "text", v: text.slice(last) });
  return out;
}

const LIST = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;

function list(lines, start) {
  const first = lines[start].match(LIST), indent = first[1].length;
  const items = [];
  let i = start;
  while (i < lines.length) {
    const m = lines[i].match(LIST);
    if (!m) {
      if (lines[i].trim() && /^\s+/.test(lines[i]) && items.length) { items[items.length - 1].c.push({ k: "text", v: " " }, ...inline(lines[i].trim())); i++; continue; }
      const nextItem = i + 1 < lines.length ? lines[i + 1].match(LIST) : null;
      if (!lines[i].trim() && nextItem && nextItem[1].length >= indent) { i++; continue; }
      break;
    }
    if (m[1].length < indent) break;
    if (m[1].length > indent) {
      const sub = list(lines, i);
      if (items.length) items[items.length - 1].sub.push(sub.node);
      i = sub.next;
      continue;
    }
    items.push({ c: inline(m[3]), sub: [] });
    i++;
  }
  return { node: { k: "list", ordered: /\d/.test(first[2]), items }, next: i };
}

export function parse(src) {
  const blocks = [];
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    let m = line.match(/^\s*(```+|~~~+)/);
    if (m) {
      const buf = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(m[1])) buf.push(lines[i++]);
      i++;
      blocks.push({ k: "pre", v: buf.join("\n") });
      continue;
    }
    m = line.match(/^(#{1,6})\s+(.*)$/);
    if (m) { blocks.push({ k: "h", level: Math.min(4, m[1].length), c: inline(m[2]) }); i++; continue; }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { blocks.push({ k: "hr" }); i++; continue; }
    if (/^\s*>/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ""));
      blocks.push({ k: "quote", c: parse(buf.join("\n")) });
      continue;
    }
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => inline(c.trim()));
      const head = cells(line), rows = [];
      i += 2;
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
      blocks.push({ k: "table", head, rows });
      continue;
    }
    if (LIST.test(line)) { const r = list(lines, i); blocks.push(r.node); i = r.next; continue; }
    const buf = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|\s*(```|~~~)|\s*>)/.test(lines[i]) && !LIST.test(lines[i])) buf.push(lines[i++]);
    blocks.push({ k: "p", c: inline(buf.join(" ")) });
  }
  return blocks;
}

// ---------------------------------------------------------------- rendering

/** Inline nodes as html; `wiki(name)` renders a [[link]] to another memory. */
export function renderInline(nodes, wiki) {
  return nodes.map((n) => {
    if (n.k === "text") return html`${n.v}`;
    if (n.k === "code") return html`<code>${n.v}</code>`;
    if (n.k === "strong") return html`<strong>${renderInline(n.c, wiki)}</strong>`;
    if (n.k === "em") return html`<em>${renderInline(n.c, wiki)}</em>`;
    if (n.k === "wiki") return wiki(n.name);
    return html`<a href="${n.href}" target="_blank" rel="noopener noreferrer">${n.text}</a>`;
  });
}

export function renderBlocks(blocks, wiki) {
  const ins = (c) => renderInline(c, wiki);
  return blocks.map((b) => {
    if (b.k === "p") return html`<p>${ins(b.c)}</p>`;
    if (b.k === "h") return html([`<h${b.level}>`, `</h${b.level}>`], ins(b.c));
    if (b.k === "hr") return html`<hr>`;
    if (b.k === "pre") return html`<pre><code>${b.v}</code></pre>`;
    if (b.k === "quote") return html`<blockquote>${renderBlocks(b.c, wiki)}</blockquote>`;
    if (b.k === "list") {
      const items = b.items.map((it) => html`<li>${ins(it.c)}${it.sub.length ? renderBlocks(it.sub, wiki) : ""}</li>`);
      return b.ordered ? html`<ol>${items}</ol>` : html`<ul>${items}</ul>`;
    }
    return html`<div class="md-table"><table>
      <thead><tr>${b.head.map((c) => html`<th>${ins(c)}</th>`)}</tr></thead>
      <tbody>${b.rows.map((r) => html`<tr>${r.map((c) => html`<td>${ins(c)}</td>`)}</tr>`)}</tbody>
    </table></div>`;
  });
}
