<script lang="ts" generics="K extends string">
  // Stacked weekly columns. Rounded tops sit on a shared baseline, 2px gaps separate segments,
  // and hovering a week shows its numbers; the table view shows them all.
  import { DAY } from "$lib/format";

  type Bucket = { from: Date; n: Record<K, number> };
  let { buckets, series, colors, labels, empty = "Nothing in these weeks." }: {
    buckets: Bucket[];
    series: K[];
    colors: Record<K, string>;
    labels: Record<K, string>;
    empty?: string;
  } = $props();

  let width = $state(640);
  let hover = $state<number | null>(null);
  let table = $state(false);
  const H = 180, padL = 28, padB = 24, padT = 10;
  const totals = $derived(buckets.map((b) => series.reduce((s, k) => s + b.n[k], 0)));
  const max = $derived(Math.max(2, ...totals));
  const step = $derived(Math.max(1, Math.ceil(max / 3)));
  const ticks = $derived(Array.from({ length: Math.floor(max / step) + 1 }, (_, i) => i * step));
  const bw = $derived((width - padL) / Math.max(1, buckets.length));
  const inner = $derived(Math.max(6, Math.min(22, bw - 12)));
  // a date label needs about 52px; count back from the latest week so it always has one
  const labelStep = $derived(Math.max(1, Math.ceil(52 / bw)));
  const y = (v: number) => padT + (H - padT - padB) * (1 - v / max);
  const label = (d: Date) => d.toLocaleDateString(undefined, { day: "numeric", month: "short" });

  function segments(i: number) {
    const b = buckets[i], x = padL + i * bw + (bw - inner) / 2, out: { k: K; d: string }[] = [];
    let acc = 0;
    const present = series.filter((k) => b.n[k]);
    present.forEach((k, j) => {
      const y0 = y(acc), y1 = y(acc + b.n[k]);
      acc += b.n[k];
      const h = Math.max(1, y0 - y1 - (j < present.length - 1 ? 2 : 0));  // the 2px gap above each segment but the top one
      const top = j === present.length - 1, r = Math.min(4, h, inner / 2);
      out.push({ k, d: top ? `M${x},${y0} V${y0 - h + r} Q${x},${y0 - h} ${x + r},${y0 - h} H${x + inner - r} Q${x + inner},${y0 - h} ${x + inner},${y0 - h + r} V${y0} Z` : `M${x},${y0} V${y0 - h} H${x + inner} V${y0} Z` });
    });
    return out;
  }
  const tipX = $derived(hover == null ? 0 : Math.min(width - 170, Math.max(0, padL + hover * bw + bw / 2 - 85)));
  const weekEnd = (d: Date) => new Date(+d + 6 * DAY);
</script>

<div class="relative min-w-0">
  <div class="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-ink-2">
    {#each series as k (k)}
      <span class="inline-flex items-center gap-1.5"><i class="size-2 rounded-full" style:background={colors[k]}></i>{labels[k]}
        <b class="font-semibold text-ink tabular-nums">{buckets.reduce((s, b) => s + b.n[k], 0)}</b></span>
    {/each}
    <button class="ml-auto text-xs text-ink-3 hover:text-ink" onclick={() => (table = !table)}>{table ? "Show chart" : "Show as table"}</button>
  </div>
  {#if table}
    <div class="overflow-x-auto">
      <table class="w-full text-[12.5px] tabular-nums">
        <thead><tr class="text-ink-3"><th class="py-1 pr-4 text-left font-medium">Week of</th>{#each series as k (k)}<th class="px-2 text-right font-medium">{labels[k]}</th>{/each}<th class="pl-2 text-right font-medium">Total</th></tr></thead>
        <tbody>{#each buckets as b, i (i)}<tr class="border-t border-line-soft"><td class="py-1 pr-4">{label(b.from)}</td>{#each series as k (k)}<td class="px-2 text-right text-ink-2">{b.n[k] || ""}</td>{/each}<td class="pl-2 text-right">{totals[i]}</td></tr>{/each}</tbody>
      </table>
    </div>
  {:else if totals.every((t) => !t)}
    <p class="py-10 text-center text-[13px] text-ink-3">{empty}</p>
  {:else}
    <!-- the drawing is as wide as its box, measured, so text and bars stay 1:1 at any width -->
    <div bind:clientWidth={width}>
    <svg viewBox="0 0 {width} {H}" width="100%" height={H} class="block overflow-visible" role="img" aria-label="Per week, by {Object.values(labels).join(', ')}" onmouseleave={() => (hover = null)}>
      {#each ticks as t (t)}
        <line x1={padL} x2={width} y1={y(t)} y2={y(t)} class="stroke-line-soft" />
        <text x={padL - 8} y={y(t) + 4} text-anchor="end" class="fill-ink-3 text-[11px] tabular-nums">{t}</text>
      {/each}
      {#each buckets as b, i (i)}
        <g role="presentation" onmouseenter={() => (hover = i)}>
          <rect x={padL + i * bw} y={padT} width={bw} height={H - padT - padB} class={hover === i ? "fill-hover" : "fill-transparent"} />
          {#each segments(i) as s (s.k)}<path d={s.d} style:fill={colors[s.k]} />{/each}
        </g>
        {#if i % labelStep === (buckets.length - 1) % labelStep}
          <text x={padL + i * bw + bw / 2} y={H - 6} text-anchor="middle" class="fill-ink-3 text-[11px]">{label(b.from)}</text>
        {/if}
      {/each}
      <line x1={padL} x2={width} y1={y(0)} y2={y(0)} class="stroke-line" />
    </svg>
    </div>
    {#if hover != null}
      {@const b = buckets[hover]}
      <div class="pointer-events-none absolute top-8 z-10 w-[170px] rounded-ctl border border-line bg-surface px-3 py-2 text-xs shadow-pop" style:left="{tipX}px">
        <div class="mb-1 font-medium">{label(b.from)} – {label(weekEnd(b.from))}</div>
        {#each series.filter((k) => b.n[k]) as k (k)}
          <div class="flex items-center gap-1.5 text-ink-2"><i class="size-2 rounded-full" style:background={colors[k]}></i><span class="flex-1">{labels[k]}</span><span class="text-ink tabular-nums">{b.n[k]}</span></div>
        {:else}<div class="text-ink-3">None</div>{/each}
      </div>
    {/if}
  {/if}
</div>
