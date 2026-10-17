<script lang="ts">
  // Types as a row of toggles: any number can be on; All turns them all off.
  import { app } from "$lib/store.svelte";
  import TypeDot from "./TypeDot.svelte";
  import type { MemoryType } from "$lib/types";

  const def = $derived(app.filterDefs.find((d) => d.key === "type")!);
  const item = "inline-flex min-w-0 items-center gap-1.5 rounded-[7px] text-[13px] text-ink-2 transition-colors hover:text-ink aria-pressed:bg-surface aria-pressed:font-semibold aria-pressed:text-ink aria-pressed:shadow-[0_0_0_1px_var(--line),0_1px_2px_rgb(0_0_0/0.04)]";
</script>

<div role="group" aria-label="Type" class="flex w-full rounded-[9px] bg-chip p-0.5">
  <button class="{item} h-7 flex-auto justify-center px-2" aria-pressed={!app.filters.type.length} onclick={() => app.setList("type", [])}>All</button>
  {#each def.options as o (o.value)}
    <button class="{item} h-7 flex-auto justify-center px-1.5 capitalize {!o.count && !app.filters.type.includes(o.value) ? 'opacity-50' : ''}"
      aria-pressed={app.filters.type.includes(o.value)} title="{o.count} {o.value}" onclick={() => app.toggle("type", o.value)}>
      <TypeDot type={o.value as MemoryType} /><span class="truncate">{o.label}</span>
    </button>
  {/each}
</div>
