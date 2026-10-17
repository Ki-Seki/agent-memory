<script lang="ts">
  import Check from "@lucide/svelte/icons/check";
  import ChevronDown from "@lucide/svelte/icons/chevron-down";
  import { Select } from "bits-ui";

  let { value, items, onchange, label, placeholder = "Choose…", class: cls = "" }: {
    value: string;
    items: { value: string; label: string }[];
    onchange: (v: string) => void;
    label: string;
    placeholder?: string;
    class?: string;
  } = $props();
  const shown = $derived(items.find((i) => i.value === value)?.label);
</script>

<Select.Root type="single" {value} onValueChange={onchange} {items}>
  <Select.Trigger aria-label={label} class="inline-flex h-8 min-w-0 items-center justify-between gap-2 rounded-ctl border border-line bg-surface px-3 text-[13px] text-ink hover:border-ink-3 data-placeholder:text-ink-3 {cls}">
    <span class="truncate">{shown ?? placeholder}</span>
    <ChevronDown class="size-3.5 shrink-0 text-ink-3" />
  </Select.Trigger>
  <Select.Portal>
    <Select.Content sideOffset={4} class="z-50 max-h-80 min-w-(--bits-select-anchor-width) overflow-auto rounded-[10px] border border-line bg-surface p-1 shadow-pop animate-in fade-in-0 zoom-in-95">
      <Select.Viewport>
        {#each items as item (item.value)}
          <Select.Item value={item.value} label={item.label} class="flex h-8 cursor-default items-center gap-2 rounded-md px-2 text-[13px] text-ink outline-none data-highlighted:bg-hover">
            {#snippet children({ selected })}
              <span class="flex-1 truncate">{item.label}</span>
              {#if selected}<Check class="size-3.5 text-accent" />{/if}
            {/snippet}
          </Select.Item>
        {/each}
      </Select.Viewport>
    </Select.Content>
  </Select.Portal>
</Select.Root>
