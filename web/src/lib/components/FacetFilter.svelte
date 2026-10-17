<script lang="ts">
  // One filter as a quiet button that opens a checklist: tick any number of values.
  import Check from "@lucide/svelte/icons/check";
  import ChevronDown from "@lucide/svelte/icons/chevron-down";
  import X from "@lucide/svelte/icons/x";
  import { Command, Popover } from "bits-ui";
  import type { ListFilter } from "$lib/filters";
  import { placeShort } from "$lib/format";
  import { app } from "$lib/store.svelte";

  let { def }: { def: ListFilter } = $props();
  let open = $state(false);
  const values = $derived(app.filters[def.key]);
  const name = (v: string) => def.options.find((o) => o.value === v)?.label ?? v;
  const short = (v: string) => (v.startsWith("place:") ? placeShort(v.slice(6)) : name(v));
  const shown = $derived(!values.length ? def.any : values.length === 1 ? short(values[0]) : `${short(values[0])} +${values.length - 1}`);
</script>

<span class="inline-flex h-8 items-center rounded-ctl {values.length ? 'bg-accent-soft' : open ? 'bg-hover' : 'hover:bg-hover'}">
  <Popover.Root bind:open>
    <Popover.Trigger title={values.length ? `${def.label}: ${values.map(name).join(", ")}` : undefined}
      class="inline-flex h-8 items-center gap-1.5 rounded-ctl pl-2.5 text-[13px] {values.length ? 'pr-1 text-accent' : 'pr-2 text-ink-3'}">
      {def.label}
      <span class="max-w-40 truncate {values.length ? 'font-semibold' : 'text-ink'}">{shown}</span>
      {#if !values.length}<ChevronDown class="size-3.5" />{/if}
    </Popover.Trigger>
    <Popover.Portal>
      <Popover.Content align="start" sideOffset={4} class="z-50 w-72 rounded-[10px] border border-line bg-surface shadow-pop outline-none animate-in fade-in-0 zoom-in-95">
        <Command.Root loop>
          {#if def.search}
            <Command.Input placeholder="Find a {def.label.toLowerCase()}" class="h-10 w-full border-b border-line bg-transparent px-3 text-[13px] outline-none placeholder:text-ink-3" />
          {/if}
          <Command.List class="max-h-72 overflow-y-auto p-1">
            <Command.Viewport>
              <Command.Empty class="px-2 py-6 text-center text-[13px] text-ink-3">Nothing matches.</Command.Empty>
              {#each def.options as o (o.value)}
                {@const on = values.includes(o.value)}
                <Command.Item value={o.label} keywords={[o.value]} onSelect={() => app.toggle(def.key, o.value)}
                  class="flex h-8 cursor-default items-center gap-2.5 rounded-md px-2 text-[13px] outline-none data-selected:bg-hover {!o.count && !on ? 'text-ink-3' : 'text-ink'}">
                  <span class="grid size-4 shrink-0 place-items-center rounded-[4px] border-[1.5px] {on ? 'border-accent bg-accent' : 'border-ink-3'}">
                    {#if on}<Check class="size-3 text-accent-ink" strokeWidth={3} />{/if}
                  </span>
                  <span class="flex-1 truncate">{o.label}</span>
                  <span class="text-xs text-ink-3 tabular-nums">{o.count}</span>
                </Command.Item>
              {/each}
            </Command.Viewport>
          </Command.List>
          {#if values.length}
            <div class="border-t border-line p-1">
              <button class="h-8 w-full rounded-md text-[13px] text-ink-2 hover:bg-hover hover:text-ink" onclick={() => app.setList(def.key, [])}>Clear {def.label.toLowerCase()}</button>
            </div>
          {/if}
        </Command.Root>
      </Popover.Content>
    </Popover.Portal>
  </Popover.Root>
  {#if values.length}
    <button class="mr-1 grid size-6 place-items-center rounded-md text-accent hover:bg-accent-soft" aria-label="Clear {def.label.toLowerCase()}" onclick={() => app.setList(def.key, [])}><X class="size-3.5" /></button>
  {/if}
</span>
