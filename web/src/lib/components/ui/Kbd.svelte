<script lang="ts">
  import type { Snippet } from "svelte";
  let { children }: { children: Snippet } = $props();
</script>

<kbd class="inline-grid h-5 min-w-5 place-items-center rounded border border-line px-1 font-mono text-[11px] text-ink-3">{@render children()}</kbd>
