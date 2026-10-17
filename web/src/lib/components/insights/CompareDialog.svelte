<script lang="ts">
  // Two similar memories side by side, to keep one, open either, or delete one.
  import X from "@lucide/svelte/icons/x";
  import { Dialog } from "bits-ui";
  import { longDay } from "$lib/format";
  import { parse } from "$lib/markdown";
  import { app } from "$lib/store.svelte";
  import type { Memory } from "$lib/types";
  import Blocks from "../Blocks.svelte";
  import TypeDot from "../TypeDot.svelte";
  import Button from "../ui/Button.svelte";

  let { pair, onclose }: { pair: [Memory, Memory, number]; onclose: () => void } = $props();
  async function remove(m: Memory) { onclose(); await app.remove([m.id]); }
  function open(m: Memory) { onclose(); app.go("memories"); app.openMemory(m.id); }
</script>

<Dialog.Root open onOpenChange={(o) => !o && onclose()}>
  <Dialog.Portal>
    <Dialog.Overlay class="fixed inset-0 z-50 bg-black/30 animate-in fade-in-0" />
    <Dialog.Content class="fixed top-1/2 left-1/2 z-50 flex max-h-[min(760px,calc(100vh-48px))] w-[min(1040px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 flex-col rounded-card border border-line bg-surface shadow-pop animate-in fade-in-0 zoom-in-95">
      <div class="flex items-center gap-3 border-b border-line px-5 py-3">
        <Dialog.Title class="flex-1 text-[15px] font-semibold">Compare two similar memories</Dialog.Title>
        <span class="text-xs text-ink-3">{Math.round(pair[2] * 100)}% alike</span>
        <Dialog.Close class="grid size-7 place-items-center rounded-md text-ink-2 hover:bg-hover" aria-label="Close"><X class="size-4" /></Dialog.Close>
      </div>
      <div class="grid min-h-0 flex-1 grid-cols-1 overflow-auto md:grid-cols-2">
        {#each [pair[0], pair[1]] as m, i (m.id)}
          <section class="flex min-w-0 flex-col p-5 {i ? 'border-t border-line md:border-t-0 md:border-l' : ''}">
            <h3 class="text-[16px] leading-snug font-semibold">{m.description}</h3>
            <div class="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-ink-3"><TypeDot type={m.type} label />·<span>{m.scope === "global" ? "Everywhere" : m.place}</span>·<span>{longDay(m.created)}</span></div>
            <div class="md mt-4 flex-1 !text-[14px]"><Blocks blocks={parse(m.body)} /></div>
            <div class="mt-5 flex gap-2">
              <Button size="sm" onclick={() => open(m)}>Open</Button>
              <Button size="sm" variant="ghost" class="text-bad hover:text-bad" onclick={() => remove(m)}>Delete this one</Button>
            </div>
          </section>
        {/each}
      </div>
    </Dialog.Content>
  </Dialog.Portal>
</Dialog.Root>
