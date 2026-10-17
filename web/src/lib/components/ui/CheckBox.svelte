<script lang="ts">
  import Check from "@lucide/svelte/icons/check";
  import { Checkbox } from "bits-ui";

  let { checked, onchange, label, class: cls = "" }: { checked: boolean; onchange: (v: boolean) => void; label: string; class?: string } = $props();
</script>

<Checkbox.Root {checked} onCheckedChange={onchange} aria-label={label} onclick={(e) => e.stopPropagation()}
  class="grid size-4 shrink-0 place-items-center rounded-[4px] border-[1.5px] border-ink-3 bg-surface transition-colors data-[state=checked]:border-accent data-[state=checked]:bg-accent {cls}">
  {#snippet children({ checked })}
    {#if checked}<Check class="size-3 text-accent-ink" strokeWidth={3} />{/if}
  {/snippet}
</Checkbox.Root>
