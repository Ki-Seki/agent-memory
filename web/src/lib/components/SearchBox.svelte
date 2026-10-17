<script lang="ts">
  import Search from "@lucide/svelte/icons/search";
  import X from "@lucide/svelte/icons/x";
  import { app } from "$lib/store.svelte";
  import Kbd from "./ui/Kbd.svelte";


  function onkeydown(e: KeyboardEvent) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); app.moveCursor(e.key === "ArrowDown" ? 1 : -1); }
    else if (e.key === "Enter") { e.preventDefault(); app.openCursor(); }
    else if (e.key === "Escape") { e.stopPropagation(); if (app.q) app.search(""); else (e.target as HTMLInputElement).blur(); }
  }
</script>

<label class="relative block">
  <Search class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" />
  <input id="q" type="search" placeholder="Search memories" autocomplete="off" spellcheck="false" value={app.q} oninput={(e) => app.search(e.currentTarget.value)} {onkeydown}
    class="h-8 w-full rounded-ctl border border-line bg-surface pr-10 pl-9 text-[13px] text-ink outline-none placeholder:text-ink-3 focus:border-accent focus:ring-3 focus:ring-accent-soft [&::-webkit-search-cancel-button]:hidden" />
  <span class="absolute top-1/2 right-2.5 -translate-y-1/2">
    {#if app.q}
      <button class="grid size-5 place-items-center rounded text-ink-3 hover:bg-hover hover:text-ink" aria-label="Clear search" onclick={() => app.search("")}><X class="size-3.5" /></button>
    {:else}<Kbd>/</Kbd>{/if}
  </span>
</label>
