<script lang="ts">
  import type { Snippet } from "svelte";
  import Button from "./Button.svelte";
  import Tip from "./Tip.svelte";

  let { label, onclick, size = "icon-sm", side = "bottom", class: cls = "", children: icon }: { label: string; onclick?: (e: MouseEvent) => void; size?: "icon" | "icon-sm"; side?: "top" | "bottom" | "left" | "right"; class?: string; children: Snippet } = $props();
</script>

<Tip text={label} {side}>
  {#snippet children(props)}
    <Button {...props} variant="ghost" {size} aria-label={label} {onclick} class={cls}>{@render icon()}</Button>
  {/snippet}
</Tip>
