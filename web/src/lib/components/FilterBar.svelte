<script lang="ts">
  import { app } from "$lib/store.svelte";
  import AddedFilter from "./AddedFilter.svelte";
  import FacetFilter from "./FacetFilter.svelte";
  import TypeToggle from "./TypeToggle.svelte";

  const facets = $derived(app.filterDefs.filter((d) => d.key !== "type"));
  const typeDef = $derived(app.filterDefs.find((d) => d.key === "type")!);
</script>

<!-- the type toggles need about 328px; a narrower list shows Type as a menu like the other filters -->
<div class="@container grid grid-cols-[minmax(0,1fr)] gap-2">
  <div class="@max-[20.5rem]:hidden"><TypeToggle /></div>
  <div class="-ml-2.5 flex flex-wrap items-center gap-0.5">
    <span class="@min-[20.5rem]:hidden"><FacetFilter def={typeDef} /></span>
    {#each facets as def (def.key)}
      {#if def.key !== "status"}<FacetFilter {def} />{/if}
    {/each}
    <AddedFilter />
    {#each facets as def (def.key)}
      {#if def.key === "status"}<FacetFilter {def} />{/if}
    {/each}
    {#if app.filtering > 1}
      <button class="h-7 rounded-md px-2 text-[13px] text-accent hover:bg-accent-soft" onclick={() => app.clearFilters()}>Clear all</button>
    {/if}
  </div>
</div>
