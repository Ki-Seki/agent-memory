<script lang="ts">
  // Said only when something is wrong: commits waiting to be pushed.
  import { plural } from "$lib/format";
  import { app } from "$lib/store.svelte";
</script>

{#if app.unpushed}
  <button class="inline-flex items-center gap-1.5 text-[12.5px] text-warn hover:underline" title="Commits a hook or this page made but has not pushed yet" onclick={() => app.go("settings")}>
    <i class="size-[7px] rounded-full bg-warn"></i>{plural(app.unpushed, "change")} not pushed
  </button>
{/if}
