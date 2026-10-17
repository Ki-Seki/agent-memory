// The Markdown memories use, parsed to a small tree that Svelte renders (no raw HTML ever reaches the page).
export type Inline =
  | { k: "text"; v: string }
  | { k: "code"; v: string }
  | { k: "strong" | "em"; c: Inline[] }
  | { k: "wiki"; name: string }
  | { k: "link"; text: string; href: string };
export interface Item { c: Inline[]; sub: Block[] }
export type Block =
  | { k: "p"; c: Inline[] }
  | { k: "h"; level: number; c: Inline[] }
  | { k: "hr" }
  | { k: "pre"; v: string }
  | { k: "quote"; c: Block[] }
  | { k: "list"; ordered: boolean; items: Item[] }
  | { k: "table"; head: Inline[][]; rows: Inline[][][] };

const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\[\[[^\]]+\]\])|(\[[^\]]+\]\((?:https?:\/\/)[^)\s]+\))|(\*[^*\s][^*]*\*)|(https?:\/\/[^\s<>()]+)/g;

export function inline(text: string): Inline[] {
  const out: Inline[] = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index! > last) out.push({ k: "text", v: text.slice(last, m.index) });
    const s = m[0];
    if (m[1]) out.push({ k: "code", v: s.slice(1, -1) });
    else if (m[2]) out.push({ k: "strong", c: inline(s.slice(2, -2)) });
    else if (m[3]) out.push({ k: "wiki", name: s.slice(2, -2) });
    else if (m[4]) { const mm = s.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/)!; out.push({ k: "link", text: mm[1], href: mm[2] }); }
    else if (m[5]) out.push({ k: "em", c: inline(s.slice(1, -1)) });
    else out.push({ k: "link", text: s, href: s });
    last = m.index! + s.length;
  }
  if (last < text.length) out.push({ k: "text", v: text.slice(last) });
  return out;
}

const LIST = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;

function list(lines: string[], start: number): { node: Block; next: number } {
  const first = lines[start].match(LIST)!, indent = first[1].length;
  const items: Item[] = [];
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

export function parse(src: string): Block[] {
  const blocks: Block[] = [];
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    let m = line.match(/^\s*(```+|~~~+)/);
    if (m) {
      const buf: string[] = [];
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
      const buf: string[] = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ""));
      blocks.push({ k: "quote", c: parse(buf.join("\n")) });
      continue;
    }
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      const cells = (l: string) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => inline(c.trim()));
      const head = cells(line), rows: Inline[][][] = [];
      i += 2;
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
      blocks.push({ k: "table", head, rows });
      continue;
    }
    if (LIST.test(line)) { const r = list(lines, i); blocks.push(r.node); i = r.next; continue; }
    const buf: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|\s*(```|~~~)|\s*>)/.test(lines[i]) && !LIST.test(lines[i])) buf.push(lines[i++]);
    blocks.push({ k: "p", c: inline(buf.join(" ")) });
  }
  return blocks;
}
