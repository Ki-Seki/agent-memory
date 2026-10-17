<script lang="ts">
  // Whatever goes where a memory opens: the memory, its edit form, or the new-memory form.
  import { app } from "$lib/store.svelte";
  import MemoryDetail from "./MemoryDetail.svelte";
  import MemoryForm from "./MemoryForm.svelte";

</script>

{#if app.mode !== "view" && app.draft}
  <MemoryForm />
{:else if app.open}
  {#key app.open.id}<MemoryDetail m={app.open} />{/key}
{/if}
