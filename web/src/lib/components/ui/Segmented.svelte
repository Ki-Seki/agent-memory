<script lang="ts">
  // A row of options where one is on. Each option may show a leading dot or icon.
  import { ToggleGroup } from "bits-ui";
  import type { Snippet } from "svelte";

  let { value, options, onchange, label, size = "md", lead }: {
    value: string;
    options: { value: string; label: string }[];
    onchange: (v: string) => void;
    label: string;
    size?: "sm" | "md";
    lead?: Snippet<[string]>;
  } = $props();
</script>

<ToggleGroup.Root type="single" {value} onValueChange={(v) => v && onchange(v)} aria-label={label} class="inline-flex rounded-[9px] bg-chip p-0.5">
  {#each options as o (o.value)}
    <ToggleGroup.Item value={o.value} class="inline-flex items-center gap-1.5 rounded-[7px] px-2.5 text-[13px] text-ink-2 transition-colors hover:text-ink data-[state=on]:bg-surface data-[state=on]:font-semibold data-[state=on]:text-ink data-[state=on]:shadow-[0_0_0_1px_var(--line),0_1px_2px_rgb(0_0_0/0.04)] {size === 'sm' ? 'h-6' : 'h-7'}">
      {@render lead?.(o.value)}{o.label}
    </ToggleGroup.Item>
  {/each}
</ToggleGroup.Root>
