<script lang="ts">
  import type { MemoryType } from "$lib/types";
  let { type, label = false }: { type: MemoryType; label?: boolean } = $props();
  const COLOR: Record<MemoryType, string> = { feedback: "bg-t-feedback", reference: "bg-t-reference", project: "bg-t-project", user: "bg-t-user" };
</script>

{#if label}
  <span class="inline-flex items-center gap-1.5"><i class="size-[7px] shrink-0 rounded-full {COLOR[type]}"></i>{type}</span>
{:else}
  <i class="inline-block size-[7px] shrink-0 rounded-full {COLOR[type]}" aria-hidden="true"></i>
{/if}
