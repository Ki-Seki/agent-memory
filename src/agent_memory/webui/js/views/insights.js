// Insights: totals, what was added and changed week by week, where memories load and who wrote them,
// pairs that read alike, and the index a session would get at one place.
import { stale, TYPES } from "../filters.js";
import { DAY, placeShort, plural } from "../format.js";
import { attrs, cx, html } from "../h.js";
import { icon } from "../icons.js";
import { app } from "../store.js";
import { select, typeDot } from "./ui.js";

const WEEKS = 12;

function weeks(series, items) {
  const start = new Date(Date.now() - (WEEKS - 1) * 7 * DAY);
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7));  // Monday
  const out = Array.from({ length: WEEKS }, (_, i) => ({ from: new Date(+start + i * 7 * DAY), n: Object.fromEntries(series.map((k) => [k, 0])) }));
  for (const it of items) { const i = Math.floor((Date.parse(it.date) - +start) / (7 * DAY)); if (i >= 0 && i < WEEKS) it.add(out[i].n); }
  return out;
}

// ---------------------------------------------------------------- the weekly chart

/**
 * Stacked weekly columns. Rounded tops sit on a shared baseline, 2px gaps separate segments, and
 * hovering a week shows its numbers; the table view shows them all. The drawing is as wide as its box
 * (measured by main.js), so text and bars stay 1:1 at any width.
 */
function chart(id, buckets, series, colors, labels, empty) {
  const width = app.insights.width?.[id] ?? 640;
  const hover = app.insights.hover[id];
  const table = app.insights.table?.[id];
  const H = 180, padL = 28, padB = 24, padT = 10;
  const totals = buckets.map((b) => series.reduce((s, k) => s + b.n[k], 0));
  const max = Math.max(2, ...totals);
  const step = Math.max(1, Math.ceil(max / 3));
  const ticks = Array.from({ length: Math.floor(max / step) + 1 }, (_, i) => i * step);
  const bw = (width - padL) / Math.max(1, buckets.length);
  const inner = Math.max(6, Math.min(22, bw - 12));
  const labelStep = Math.max(1, Math.ceil(52 / bw));  // a date label needs about 52px; count back from the latest week
  const y = (v) => padT + (H - padT - padB) * (1 - v / max);
  const label = (d) => d.toLocaleDateString(undefined, { day: "numeric", month: "short" });

  function segments(i) {
    const b = buckets[i], x = padL + i * bw + (bw - inner) / 2, out = [];
    let acc = 0;
    const present = series.filter((k) => b.n[k]);
    present.forEach((k, j) => {
      const y0 = y(acc), y1 = y(acc + b.n[k]);
      acc += b.n[k];
      const h = Math.max(1, y0 - y1 - (j < present.length - 1 ? 2 : 0));  // the 2px gap above each segment but the top one
      const top = j === present.length - 1, r = Math.min(4, h, inner / 2);
      out.push(html`<path d="${top ? `M${x},${y0} V${y0 - h + r} Q${x},${y0 - h} ${x + r},${y0 - h} H${x + inner - r} Q${x + inner},${y0 - h} ${x + inner},${y0 - h + r} V${y0} Z` : `M${x},${y0} V${y0 - h} H${x + inner} V${y0} Z`}" style="fill:${colors[k]}"/>`);
    });
    return out;
  }

  const legend = html`<div class="legend">
    ${series.map((k) => html`<span><i class="dot" style="background:${colors[k]}"></i>${labels[k]} <b>${buckets.reduce((s, b) => s + b.n[k], 0)}</b></span>`)}
    <button type="button" class="link-quiet" data-act="chartTable" data-arg="${id}">${table ? "Show chart" : "Show as table"}</button>
  </div>`;
  if (table) {
    return html`<div class="chart">${legend}<div class="table-wrap"><table class="nums">
      <thead><tr><th>Week of</th>${series.map((k) => html`<th>${labels[k]}</th>`)}<th>Total</th></tr></thead>
      <tbody>${buckets.map((b, i) => html`<tr><td>${label(b.from)}</td>${series.map((k) => html`<td>${b.n[k] || ""}</td>`)}<td>${totals[i]}</td></tr>`)}</tbody>
    </table></div></div>`;
  }
  if (totals.every((t) => !t)) return html`<div class="chart">${legend}<p class="chart-empty">${empty}</p></div>`;
  const tipX = hover == null ? 0 : Math.min(width - 170, Math.max(0, padL + hover * bw + bw / 2 - 85));
  const b = hover == null ? null : buckets[hover];
  return html`<div class="chart">${legend}
    <div class="chart-box" data-chart="${id}">
      <svg viewBox="0 0 ${width} ${H}" width="100%" height="${H}" role="img" aria-label="Per week, by ${Object.values(labels).join(", ")}">
        ${ticks.map((t) => html`<line x1="${padL}" x2="${width}" y1="${y(t)}" y2="${y(t)}" class="grid-line"/><text x="${padL - 8}" y="${y(t) + 4}" text-anchor="end" class="axis">${t}</text>`)}
        ${buckets.map((bk, i) => html`<g data-week="${i}"><rect x="${padL + i * bw}" y="${padT}" width="${bw}" height="${H - padT - padB}" class="${hover === i ? "week on" : "week"}"/>${segments(i)}</g>
          ${i % labelStep === (buckets.length - 1) % labelStep ? html`<text x="${padL + i * bw + bw / 2}" y="${H - 6}" text-anchor="middle" class="axis">${label(bk.from)}</text>` : ""}`)}
        <line x1="${padL}" x2="${width}" y1="${y(0)}" y2="${y(0)}" class="base-line"/>
      </svg>
    </div>
    ${b ? html`<div class="chart-tip" style="left:${tipX}px">
      <div class="chart-tip-title">${label(b.from)} – ${label(new Date(+b.from + 6 * DAY))}</div>
      ${series.filter((k) => b.n[k]).map((k) => html`<div class="chart-tip-row"><i class="dot" style="background:${colors[k]}"></i><span class="grow">${labels[k]}</span><b>${b.n[k]}</b></div>`)}
      ${series.some((k) => b.n[k]) ? "" : html`<div class="faint">None</div>`}
    </div>` : ""}
  </div>`;
}

// ---------------------------------------------------------------- the page

const TYPE_COLORS = { feedback: "var(--t-feedback)", reference: "var(--t-reference)", project: "var(--t-project)", user: "var(--t-user)" };
const TOOL_COLORS = { claude: "color-mix(in srgb, var(--ink) 78%, transparent)", codex: "color-mix(in srgb, var(--ink) 45%, transparent)", you: "color-mix(in srgb, var(--ink) 22%, transparent)" };
const who = (tool) => (tool === "codex" ? "codex" : tool === "ui" ? "you" : "claude");

const bars = (items, act) => {
  const top = Math.max(1, items[0]?.n ?? 1);
  return html`<div class="bars">${items.map((p) => html`<button type="button" class="bar-row"${attrs({ title: p.title ? `${p.title}: ${p.n}` : null, "data-act": act, "data-arg": p.key })}>
    <span class="bar-label">${p.icon ? icon(p.icon) : ""}<span class="truncate">${p.label}</span></span>
    <span class="bar"><span style="width:${(p.n / top) * 100}%"></span></span><span class="bar-n">${p.n}</span></button>`)}</div>`;
};

export function insightsPage() {
  const M = app.M;
  const added = weeks(TYPES, M.map((m) => ({ date: m.created, add: (n) => n[m.type]++ })));
  const changes = weeks(["claude", "codex", "you"], app.insights.commits.map((c) => ({ date: c.date, add: (n) => { n[who(c.tool)] += c.added + c.changed + c.deleted; } })));
  const thisWeek = M.filter((m) => Date.now() - Date.parse(m.created) <= 7 * DAY).length;
  const tidy = M.filter((m) => m.issues.length);
  const old = M.filter(stale);
  const places = [
    { label: "Everywhere", key: "global", title: "Loads in every session", n: M.filter((m) => m.scope === "global").length, icon: "globe" },
    ...app.places.map((p) => ({ label: placeShort(p.key), key: "place:" + p.key, title: p.key, n: p.count, icon: "folder" })),
  ].sort((a, b) => b.n - a.n);
  const toolName = (t) => (t === "claude-code" ? "Claude Code" : t === "codex" ? "Codex" : t === "ui" ? "You, in this page" : t);
  const tools = [...new Set(M.map((m) => m.tool).filter(Boolean))].map((t) => ({ label: toolName(t), key: t, n: M.filter((m) => m.tool === t).length })).sort((a, b) => b.n - a.n);
  const pairs = duplicatePairs();
  const preview = app.insights.preview;
  const stats = [["Memories", M.length, "in the data repository", null], ["Added this week", thisWeek, "by Claude Code, Codex or you", null], ["Need tidying", tidy.length, tidy.length ? "differ from PROTOCOL.md" : "all follow the format", "tidy"], ["Unchanged 60+ days", old.length, "worth a second look", "stale"]];

  return html`<div class="insights">
    <div class="stats">${stats.map(([k, v, s, f]) => html`<div class="stat"><div class="stat-k">${k}</div><div class="stat-v">${v}</div>
      ${f && v > 0 ? html`<button type="button" class="stat-s link-quiet" data-act="showStatus" data-arg="${f}">${s}${icon("arrow-right")}</button>` : html`<div class="stat-s">${s}</div>`}</div>`)}</div>

    <section class="card span2"><h2>Added per week</h2>${chart("added", added, TYPES, TYPE_COLORS, Object.fromEntries(TYPES.map((t) => [t, t])), `Nothing was added in the past ${WEEKS} weeks.`)}</section>
    <section class="card"><h2>Where they load</h2>${bars(places, "showLoads")}</section>
    <section class="card"><h2>Written by</h2>${bars(tools, "showTool")}</section>

    <section class="card span2"><h2>Possible duplicates</h2><p class="card-note">Pairs that read alike; compare them side by side and keep one.</p>
      ${pairs.length ? pairs.map((p, i) => html`<div class="pair"><div class="pair-text"><span class="truncate">${p[0].description}</span><span class="truncate faint2">${p[1].description}</span></div>
        <span class="count">${Math.round(p[2] * 100)}%</span><button type="button" class="btn sm" data-act="compare" data-arg="${i}">Compare</button></div>`)
        : html`<p class="card-note">No two memories are more than 45% alike.</p>`}
    </section>

    <section class="card span2"><h2>Changes per week</h2>${chart("changes", changes, ["claude", "codex", "you"], TOOL_COLORS, { claude: "Claude Code", codex: "Codex", you: "You, in this page" }, `No memory changes in the past ${WEEKS} weeks.`)}</section>

    <section class="card span2">
      <div class="card-head"><div><h2>What an agent sees at session start</h2><p class="card-note">The index the SessionStart hook injects, for a session started in this place.</p></div>
        ${select("Place", app.insights.place, [{ value: "", label: "No particular place (global only)" }, ...app.places.map((p) => ({ value: p.key, label: p.key }))], "previewPlace", "wide")}</div>
      ${preview ? html`<div class="meter-row"><span class="meter"><span${attrs({ class: cx(preview.chars > preview.limit * 0.9 && "warn"), style: `width:${Math.min(100, (preview.chars / preview.limit) * 100)}%` })}></span></span>
        <span>${preview.chars.toLocaleString()} of ${preview.limit.toLocaleString()} characters · ${plural(preview.global, "global memory", "global memories")} + ${preview.here} for this place</span></div>
        <pre class="raw tall">${preview.text}</pre>` : ""}
    </section>

    ${tidy.length ? html`<section class="card span2"><h2>Needs tidying</h2>${tidy.map((m) => html`<button type="button" class="tidy" data-act="open" data-arg="${m.id}">${typeDot(m.type)}<span class="grow"><span class="t truncate">${m.description}</span><span class="faint truncate">${m.issues.join(" · ").replace(/\*\*/g, "")}</span></span></button>`)}</section>` : ""}
  </div>`;
}

/** The pairs shown under Possible duplicates, so Compare can find its pair by position. */
export function duplicatePairs() {
  const M = app.M, pairs = [];
  M.forEach((m, i) => m.similar.forEach((s) => { if (s.i > i && s.s >= 0.45 && M[s.i]) pairs.push([m, M[s.i], s.s]); }));
  return pairs.sort((a, b) => b[2] - a[2]).slice(0, 5);
}
