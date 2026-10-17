<script lang="ts">
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import Folder from "@lucide/svelte/icons/folder";
  import Globe from "@lucide/svelte/icons/globe";
  import { api } from "$lib/api";
  import { stale, TYPES } from "$lib/filters";
  import { DAY, placeShort, plural } from "$lib/format";
  import { app } from "$lib/store.svelte";
  import type { Commit, IndexPreview, Memory, MemoryType } from "$lib/types";
  import TypeDot from "../TypeDot.svelte";
  import Button from "../ui/Button.svelte";
  import SelectMenu from "../ui/SelectMenu.svelte";
  import CompareDialog from "./CompareDialog.svelte";
  import WeeklyChart from "./WeeklyChart.svelte";

  const WEEKS = 12;
  const M = $derived(app.M);

  function weeks<K extends string>(series: K[], items: { date: string; add: (n: Record<K, number>) => void }[]) {
    const start = new Date(Date.now() - (WEEKS - 1) * 7 * DAY);
    start.setHours(0, 0, 0, 0);
    start.setDate(start.getDate() - ((start.getDay() + 6) % 7));  // Monday
    const out = Array.from({ length: WEEKS }, (_, i) => ({ from: new Date(+start + i * 7 * DAY), n: Object.fromEntries(series.map((k) => [k, 0])) as Record<K, number> }));
    for (const it of items) { const i = Math.floor((Date.parse(it.date) - +start) / (7 * DAY)); if (i >= 0 && i < WEEKS) it.add(out[i].n); }
    return out;
  }
  const typeColors = { feedback: "var(--t-feedback)", reference: "var(--t-reference)", project: "var(--t-project)", user: "var(--t-user)" } as Record<MemoryType, string>;
  const typeLabels = Object.fromEntries(TYPES.map((t) => [t, t])) as Record<MemoryType, string>;
  const added = $derived(weeks(TYPES, M.map((m) => ({ date: m.created, add: (n: Record<MemoryType, number>) => n[m.type]++ }))));

  let commits = $state<Commit[]>([]);
  type Who = "claude" | "codex" | "you";
  const who = (tool: string | null): Who => (tool === "codex" ? "codex" : tool === "ui" ? "you" : "claude");
  const changes = $derived(weeks<Who>(["claude", "codex", "you"], commits.map((c) => ({ date: c.date, add: (n: Record<Who, number>) => { n[who(c.tool)] += c.added + c.changed + c.deleted; } }))));
  const toolColors: Record<Who, string> = { claude: "color-mix(in srgb, var(--ink) 78%, transparent)", codex: "color-mix(in srgb, var(--ink) 45%, transparent)", you: "color-mix(in srgb, var(--ink) 22%, transparent)" };

  const total = $derived(M.length);
  const thisWeek = $derived(M.filter((m) => Date.now() - Date.parse(m.created) <= 7 * DAY).length);
  const tidy = $derived(M.filter((m) => m.issues.length));
  const old = $derived(M.filter(stale));
  const places = $derived([
    { label: "Everywhere", key: "global", title: "Loads in every session", n: M.filter((m) => m.scope === "global").length, global: true },
    ...app.places.map((p) => ({ label: placeShort(p.key), key: "place:" + p.key, title: p.key, n: p.count, global: false })),
  ].sort((a, b) => b.n - a.n));
  const tools = $derived([...new Set(M.map((m) => m.tool).filter(Boolean))].map((t) => ({ label: t === "claude-code" ? "Claude Code" : t === "codex" ? "Codex" : t === "ui" ? "You, in this page" : t, key: t, n: M.filter((m) => m.tool === t).length })).sort((a, b) => b.n - a.n));
  const pairs = $derived.by(() => {
    const out: [Memory, Memory, number][] = [];
    M.forEach((m, i) => m.similar.forEach((s) => { if (s.i > i && s.s >= 0.45 && M[s.i]) out.push([m, M[s.i], s.s]); }));
    return out.sort((a, b) => b[2] - a[2]).slice(0, 5);
  });
  let comparing = $state<[Memory, Memory, number] | null>(null);

  let place = $state("");
  let preview = $state<IndexPreview | null>(null);
  $effect(() => {
    const p = place;
    api<IndexPreview>(`/api/index-preview?place=${encodeURIComponent(p)}`).then((r) => { if (p === place) preview = r; }).catch(() => (preview = null));
  });
  $effect(() => { void app.data?.stamp; api<{ commits: Commit[] }>("/api/activity").then((r) => (commits = r.commits)).catch(() => {}); });

  function show(filter: "loads" | "tool" | "status", value: string) {
    app.clearFilters(); app.setList(filter, [value]); app.go("memories");
  }
  const card = "rounded-card border border-line bg-surface p-5 max-sm:p-4";
  const h2 = "text-[13.5px] font-semibold";
</script>

<div class="grid grid-cols-1 gap-4 max-sm:gap-3 md:grid-cols-2 [&>*]:min-w-0">
  <div class="grid grid-cols-2 gap-3 md:col-span-2 xl:grid-cols-4">
    {#each [["Memories", total, "in the data repository", null], ["Added this week", thisWeek, "by Claude Code, Codex or you", null], ["Need tidying", tidy.length, tidy.length ? "differ from PROTOCOL.md" : "all follow the format", "tidy"], ["Unchanged 60+ days", old.length, "worth a second look", "stale"]] as [k, v, s, f] (k)}
      <div class="rounded-card border border-line bg-surface px-5 py-4 max-sm:px-4 max-sm:py-3">
        <div class="text-[12.5px] text-ink-2">{k}</div>
        <div class="mt-1.5 text-3xl font-semibold tracking-tight tabular-nums max-sm:text-2xl">{v}</div>
        {#if f && Number(v) > 0}
          <button class="mt-0.5 inline-flex items-center gap-1 text-xs text-ink-3 hover:text-accent" onclick={() => show("status", String(f))}>{s}<ArrowRight class="size-3" /></button>
        {:else}<div class="mt-0.5 text-xs text-ink-3">{s}</div>{/if}
      </div>
    {/each}
  </div>

  <section class="{card} md:col-span-2">
    <h2 class="{h2} mb-3">Added per week</h2>
    <WeeklyChart buckets={added} series={TYPES} colors={typeColors} labels={typeLabels} empty="Nothing was added in the past {WEEKS} weeks." />
  </section>

  <section class={card}>
    <h2 class="{h2} mb-4">Where they load</h2>
    <div class="grid gap-2.5">
      {#each places as p (p.key)}
        <button class="group grid grid-cols-[120px_minmax(0,1fr)_32px] items-center gap-3 text-left text-[13px]" title="{p.title}: {p.n}" onclick={() => show("loads", p.key)}>
          <span class="inline-flex min-w-0 items-center gap-1.5 text-ink-2 group-hover:text-ink">{#if p.global}<Globe class="size-3.5 shrink-0 text-ink-3" />{:else}<Folder class="size-3.5 shrink-0 text-ink-3" />{/if}<span class="truncate">{p.label}</span></span>
          <span class="h-2 overflow-hidden rounded bg-chip"><span class="block h-full rounded bg-ink-2 group-hover:bg-accent" style:width="{(p.n / Math.max(1, places[0].n)) * 100}%"></span></span>
          <span class="text-right text-ink-2 tabular-nums">{p.n}</span>
        </button>
      {/each}
    </div>
  </section>

  <section class={card}>
    <h2 class="{h2} mb-4">Written by</h2>
    <div class="grid gap-2.5">
      {#each tools as t (t.key)}
        <button class="group grid grid-cols-[120px_minmax(0,1fr)_32px] items-center gap-3 text-left text-[13px]" onclick={() => show("tool", t.key)}>
          <span class="truncate text-ink-2 group-hover:text-ink">{t.label}</span>
          <span class="h-2 overflow-hidden rounded bg-chip"><span class="block h-full rounded bg-ink-2 group-hover:bg-accent" style:width="{(t.n / Math.max(1, tools[0]?.n ?? 1)) * 100}%"></span></span>
          <span class="text-right text-ink-2 tabular-nums">{t.n}</span>
        </button>
      {/each}
    </div>
  </section>

  <section class="{card} md:col-span-2">
    <h2 class="{h2} mb-1">Possible duplicates</h2>
    <p class="mb-2 text-[12.5px] text-ink-3">Pairs that read alike; compare them side by side and keep one.</p>
    {#each pairs as pair (pair[0].id + pair[1].id)}
      <div class="flex items-center gap-3 border-t border-line-soft py-2.5 first-of-type:border-t-0">
        <div class="grid min-w-0 flex-1 gap-0.5 text-[13px]"><span class="truncate">{pair[0].description}</span><span class="truncate text-ink-2">{pair[1].description}</span></div>
        <span class="text-xs text-ink-3 tabular-nums">{Math.round(pair[2] * 100)}%</span>
        <Button size="sm" onclick={() => (comparing = pair)}>Compare</Button>
      </div>
    {:else}
      <p class="py-2 text-[13px] text-ink-3">No two memories are more than 45% alike.</p>
    {/each}
  </section>

  <section class="{card} md:col-span-2">
    <h2 class="{h2} mb-3">Changes per week</h2>
    <WeeklyChart buckets={changes} series={["claude", "codex", "you"] as Who[]} colors={toolColors} labels={{ claude: "Claude Code", codex: "Codex", you: "You, in this page" }} empty="No memory changes in the past {WEEKS} weeks." />
  </section>

  <section class="{card} md:col-span-2">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class={h2}>What an agent sees at session start</h2>
        <p class="mt-0.5 text-[12.5px] text-ink-3">The index the SessionStart hook injects, for a session started in this place.</p>
      </div>
      <SelectMenu label="Place" class="w-72 max-sm:w-full" value={place} onchange={(v) => (place = v)}
        items={[{ value: "", label: "No particular place (global only)" }, ...app.places.map((p) => ({ value: p.key, label: p.key }))]} />
    </div>
    {#if preview}
      <div class="mb-3 flex items-center gap-3 text-[12.5px] text-ink-3">
        <span class="h-1.5 w-44 overflow-hidden rounded bg-chip"><span class="block h-full rounded {preview.chars > preview.limit * 0.9 ? 'bg-warn' : 'bg-ink-2'}" style:width="{Math.min(100, (preview.chars / preview.limit) * 100)}%"></span></span>
        <span class="tabular-nums">{preview.chars.toLocaleString()} of {preview.limit.toLocaleString()} characters · {plural(preview.global, "global memory", "global memories")} + {preview.here} for this place</span>
      </div>
      <pre class="max-h-80 overflow-auto rounded-ctl bg-code px-4 py-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-ink-2">{preview.text}</pre>
    {/if}
  </section>

  {#if tidy.length}
    <section class="{card} md:col-span-2">
      <h2 class="{h2} mb-1">Needs tidying</h2>
      {#each tidy as m (m.id)}
        <button class="flex w-full items-start gap-3 border-t border-line-soft py-2.5 text-left first-of-type:border-t-0 hover:[&_.t]:underline" onclick={() => { app.go("memories"); app.openMemory(m.id); }}>
          <TypeDot type={m.type} /><span class="min-w-0 flex-1"><span class="t block truncate text-[13.5px]">{m.description}</span><span class="block truncate text-xs text-ink-3">{m.issues.join(" · ").replace(/\*\*/g, "")}</span></span>
        </button>
      {/each}
    </section>
  {/if}
</div>

{#if comparing}<CompareDialog pair={comparing} onclose={() => (comparing = null)} />{/if}
