<script lang="ts">
  // The order, chosen where the dates are: the label says which dates and which way they run.
  import ArrowDown from "@lucide/svelte/icons/arrow-down";
  import ArrowUp from "@lucide/svelte/icons/arrow-up";
  import Check from "@lucide/svelte/icons/check";
  import { DropdownMenu } from "bits-ui";
  import { SORTS, type Sort } from "$lib/filters";
  import { app } from "$lib/store.svelte";

  const LABEL: Record<Sort, string> = { new: "Added", old: "Added", edited: "Changed", az: "A to Z" };
</script>

{#if app.q.trim()}
  <span class="text-ink-3">Added</span>
{:else}
  <DropdownMenu.Root>
    <DropdownMenu.Trigger class="-mr-2 inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs font-medium text-ink-2 hover:bg-hover hover:text-ink" title="Change the order">
      {LABEL[app.sort]}
      {#if app.sort === "old"}<ArrowUp class="size-3.5" />{:else if app.sort !== "az"}<ArrowDown class="size-3.5" />{/if}
    </DropdownMenu.Trigger>
    <DropdownMenu.Portal>
      <DropdownMenu.Content align="end" sideOffset={4} class="z-50 w-48 rounded-[10px] border border-line bg-surface p-1 shadow-pop outline-none animate-in fade-in-0 zoom-in-95">
        <DropdownMenu.RadioGroup value={app.sort} onValueChange={(v) => app.setSort(v as Sort)}>
          {#each SORTS as [value, label] (value)}
            <DropdownMenu.RadioItem {value} class="flex h-8 cursor-default items-center gap-2 rounded-md px-2 text-[13px] text-ink outline-none data-highlighted:bg-hover">
              {#snippet children({ checked })}<span class="flex-1">{label}</span>{#if checked}<Check class="size-3.5 text-accent" />{/if}{/snippet}
            </DropdownMenu.RadioItem>
          {/each}
        </DropdownMenu.RadioGroup>
      </DropdownMenu.Content>
    </DropdownMenu.Portal>
  </DropdownMenu.Root>
{/if}
