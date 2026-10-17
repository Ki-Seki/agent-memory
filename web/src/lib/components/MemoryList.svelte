<script lang="ts">
  // The list: each memory as its description and one line of type, place and date.
  import { touched } from "$lib/filters";
  import { day, placeShort } from "$lib/format";
  import { snippet, terms } from "$lib/search";
  import { app } from "$lib/store.svelte";
  import type { Memory } from "$lib/types";
  import Highlight from "./Highlight.svelte";
  import SortMenu from "./SortMenu.svelte";
  import TypeDot from "./TypeDot.svelte";
  import Button from "./ui/Button.svelte";
  import CheckBox from "./ui/CheckBox.svelte";

  const words = $derived(terms(app.q));
  const selecting = $derived(app.picked.size > 0);
  const place = (m: Memory) => (m.scope === "global" ? "Everywhere" : placeShort(m.place));
  const date = (m: Memory) => day(app.sort === "edited" ? touched(m) : m.created);

  function click(e: MouseEvent, m: Memory) {
    if (e.metaKey || e.shiftKey || e.ctrlKey) { app.togglePick(m.id); return; }
    app.openMemory(m.id);
  }
  let box: HTMLElement | undefined = $state();
  $effect(() => {
    const k = app.cursor;
    box?.querySelector(`[data-k="${k}"]`)?.scrollIntoView({ block: "nearest" });
  });
</script>

<div bind:this={box}>
  <div class="sticky top-0 z-[1] flex h-9 items-center justify-between border-b border-line bg-panel px-4 text-xs text-ink-3">
    <span class="tabular-nums" aria-live="polite">{app.countText}</span>
    <SortMenu />
  </div>

  {#each app.groups as g, gi (gi)}
    {#if g.title && g.items.length}
      <div class="border-b border-line-soft px-4 pt-5 pb-2 text-xs font-semibold text-ink-3">{g.title}</div>
    {/if}
    {#each g.items as m (m.id)}
      {@const k = app.rows.indexOf(m)}
      {@const isOpen = app.openId === m.id}
      {@const snip = words.length ? snippet(m, words) : null}
      <div role="button" tabindex="-1" data-k={k} onclick={(e) => click(e, m)} onkeydown={(e) => e.key === "Enter" && app.openMemory(m.id)}
        class="group relative flex cursor-pointer gap-3 border-b border-line-soft px-4 py-3 transition-colors
          {app.picked.has(m.id) ? 'bg-chip' : isOpen ? 'bg-surface' : 'hover:bg-hover'}
          {isOpen ? 'shadow-[inset_2px_0_0_var(--accent)]' : k === app.cursor ? 'shadow-[inset_2px_0_0_var(--ink-3)]' : ''}">
        <span class="flex h-[21px] items-center transition-opacity {selecting || app.picked.has(m.id) ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 max-lg:hidden'}">
          <CheckBox checked={app.picked.has(m.id)} onchange={() => app.togglePick(m.id)} label="Select" />
        </span>
        <div class="min-w-0 flex-1">
          <div class="line-clamp-2 leading-[21px] font-semibold"><Highlight text={m.description} {words} /></div>
          <div class="mt-1 flex items-center gap-1.5 text-xs text-ink-3">
            <TypeDot type={m.type} label /><span>·</span><span class="truncate" title={m.scope === "global" ? "Loads in every session" : m.place}>{place(m)}</span><span>·</span><span class="shrink-0">{date(m)}</span>
          </div>
          {#if snip}<div class="mt-1 truncate text-[12.5px] text-ink-3"><Highlight text={snip} {words} /></div>{/if}
        </div>
      </div>
    {/each}
  {/each}

  {#if !app.rows.length && app.data}
    <div class="px-6 py-16 text-center text-ink-3">
      <p>{app.q.trim() ? (app.semPending ? "No word matches; searching by meaning…" : "No matches.") : app.M.length ? "No memories match these filters." : "No memories yet. Agents add them as you work."}</p>
      {#if app.filtering}<Button class="mt-3" onclick={() => app.clearFilters()}>Clear filters</Button>{/if}
    </div>
  {/if}
</div>
