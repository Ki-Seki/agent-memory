<script lang="ts">
  import { app } from "$lib/store.svelte";
  import { fly } from "svelte/transition";

  const shown = $derived(app.rows.map((m) => m.id));
  const rest = $derived(shown.filter((id) => !app.picked.has(id)).length);
  const btn = "h-7 rounded-md border border-bg/25 px-2.5 text-[13px] hover:bg-bg/15";
</script>

{#if app.picked.size}
  <div transition:fly={{ y: 10, duration: 160 }} class="fixed bottom-6 left-1/2 z-40 flex -translate-x-1/2 items-center gap-2 rounded-card bg-ink py-2 pr-2 pl-4 text-bg shadow-pop">
    <span class="mr-1 text-[13px] font-semibold">{app.picked.size} selected</span>
    {#if rest}<button class={btn} onclick={() => shown.forEach((id) => app.picked.add(id))}>Select all {shown.length}</button>{/if}
    <button class={btn} onclick={() => app.picked.clear()}>Clear</button>
    <button class="h-7 rounded-md bg-bad px-2.5 text-[13px] font-medium text-white hover:opacity-90" onclick={() => app.remove([...app.picked])}>Delete</button>
  </div>
{/if}
