<script lang="ts">
  // When a memory was added: one recent period, or a date range with either end open.
  import ChevronDown from "@lucide/svelte/icons/chevron-down";
  import X from "@lucide/svelte/icons/x";
  import { Popover } from "bits-ui";
  import { addedOptions } from "$lib/filters";
  import { app } from "$lib/store.svelte";

  let open = $state(false);
  const v = $derived(app.filters.added);
  const opts = $derived(addedOptions(app.M, app.filters, app.termSets));
  const range = $derived(v.startsWith("range:") ? v.split(":").slice(1) : ["", ""]);
  const fmt = (s: string) => new Date(`${s}T00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  const shown = $derived(!v ? "Any time" : v.startsWith("range:") ? (range[0] && range[1] ? `${fmt(range[0])} – ${fmt(range[1])}` : range[0] ? `since ${fmt(range[0])}` : `until ${fmt(range[1])}`) : (opts.find((o) => o.value === v)?.label ?? v));
  const setRange = (a: string, b: string) => app.setAdded(a || b ? `range:${a}:${b}` : "");
  const date = "h-8 min-w-0 flex-1 rounded-md border border-line bg-surface px-2 text-[12.5px] text-ink outline-none focus:border-accent";
</script>

<span class="inline-flex h-8 items-center rounded-ctl {v ? 'bg-accent-soft' : open ? 'bg-hover' : 'hover:bg-hover'}">
  <Popover.Root bind:open>
    <Popover.Trigger class="inline-flex h-8 items-center gap-1.5 rounded-ctl pl-2.5 text-[13px] {v ? 'pr-1 text-accent' : 'pr-2 text-ink-3'}">
      Added <span class="max-w-44 truncate {v ? 'font-semibold' : 'text-ink'}">{shown}</span>
      {#if !v}<ChevronDown class="size-3.5" />{/if}
    </Popover.Trigger>
    <Popover.Portal>
      <Popover.Content align="start" sideOffset={4} class="z-50 w-72 rounded-[10px] border border-line bg-surface p-1 shadow-pop outline-none animate-in fade-in-0 zoom-in-95">
        <div role="radiogroup" aria-label="Added">
          {#each opts as o (o.value)}
            {@const on = v === o.value}
            <button role="radio" aria-checked={on} onclick={() => app.setAdded(on ? "" : o.value)}
              class="flex h-8 w-full items-center gap-2.5 rounded-md px-2 text-left text-[13px] hover:bg-hover {!o.count && !on ? 'text-ink-3' : 'text-ink'}">
              <span class="grid size-4 place-items-center rounded-full border-[1.5px] {on ? 'border-accent' : 'border-ink-3'}">{#if on}<i class="size-2 rounded-full bg-accent"></i>{/if}</span>
              <span class="flex-1">{o.label}</span><span class="text-xs text-ink-3 tabular-nums">{o.count}</span>
            </button>
          {/each}
        </div>
        <div class="mt-1 border-t border-line px-2 pt-2.5 pb-2">
          <div class="mb-1.5 text-xs text-ink-3">Or between</div>
          <div class="flex items-center gap-1.5 text-ink-3">
            <input type="date" class={date} value={range[0]} max={range[1] || undefined} aria-label="Added on or after" onchange={(e) => setRange(e.currentTarget.value, range[1])} />
            –
            <input type="date" class={date} value={range[1]} min={range[0] || undefined} aria-label="Added on or before" onchange={(e) => setRange(range[0], e.currentTarget.value)} />
          </div>
        </div>
        {#if v}
          <div class="border-t border-line pt-1"><button class="h-8 w-full rounded-md text-[13px] text-ink-2 hover:bg-hover hover:text-ink" onclick={() => app.setAdded("")}>Any time</button></div>
        {/if}
      </Popover.Content>
    </Popover.Portal>
  </Popover.Root>
  {#if v}
    <button class="mr-1 grid size-6 place-items-center rounded-md text-accent hover:bg-accent-soft" aria-label="Clear added" onclick={() => app.setAdded("")}><X class="size-3.5" /></button>
  {/if}
</span>
