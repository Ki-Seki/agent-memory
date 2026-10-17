<script lang="ts">
  // A tooltip around any trigger: pass the trigger as a snippet that spreads the props it is given.
  import { Tooltip } from "bits-ui";
  import type { Snippet } from "svelte";

  let { text, side = "bottom", children }: { text: string; side?: "top" | "bottom" | "left" | "right"; children: Snippet<[Record<string, unknown>]> } = $props();
</script>

<Tooltip.Root>
  <Tooltip.Trigger>
    {#snippet child({ props })}{@render children(props)}{/snippet}
  </Tooltip.Trigger>
  <Tooltip.Portal>
    <Tooltip.Content {side} sideOffset={6} class="z-50 rounded-md bg-ink px-2 py-1 text-xs text-bg shadow-pop animate-in fade-in-0 zoom-in-95">{text}</Tooltip.Content>
  </Tooltip.Portal>
</Tooltip.Root>
