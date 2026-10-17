<script lang="ts">
  // A narrow rail (a top bar on phones), a compact list, and the open memory beside it.
  // Below 1024px the list and the memory take turns; the logo always leads back to the memories.
  import ArrowLeft from "@lucide/svelte/icons/arrow-left";
  import ChartColumn from "@lucide/svelte/icons/chart-column";
  import Plus from "@lucide/svelte/icons/plus";
  import Settings2 from "@lucide/svelte/icons/settings-2";
  import InsightsPage from "../components/insights/InsightsPage.svelte";
  import MemoryList from "../components/MemoryList.svelte";
  import MemoryPanel from "../components/MemoryPanel.svelte";
  import SettingsPage from "../components/settings/SettingsPage.svelte";
  import Button from "../components/ui/Button.svelte";
  import Tip from "../components/ui/Tip.svelte";
  import { app, type Page } from "../store.svelte";
  import Brand from "./Brand.svelte";
  import MemoriesTools from "./MemoriesTools.svelte";
  import ResizeHandle from "../components/ResizeHandle.svelte";
  import Unpushed from "./Unpushed.svelte";

  // On a wide window the reading pane is never empty: it shows the first memory until you pick one.
  // That one does not count as opened, so a narrower window then shows the list, not that memory.
  let autoId = $state<string | null>(null);
  $effect(() => {
    if (app.wide.current && app.page === "memories" && !app.openId && app.mode === "view" && app.rows.length && !app.q.trim()) {
      autoId = app.rows[0].id;
      app.openMemory(autoId);
    }
  });
  const reading = $derived((!!app.openId && app.openId !== autoId) || app.mode !== "view");
  const TITLES: Partial<Record<Page, string>> = { insights: "Insights", settings: "Settings" };
  let listPane: HTMLElement | undefined = $state();
</script>

{#snippet railButton(p: Page, label: string, Icon: typeof ChartColumn)}
  <Tip text={label} side="right">
    {#snippet children(props)}
      <button {...props} aria-label={label} aria-current={app.page === p ? "page" : undefined} onclick={() => app.go(p)}
        class="grid size-10 place-items-center rounded-[9px] transition-colors {app.page === p ? 'bg-surface text-accent shadow-[0_0_0_1px_var(--line)]' : 'text-ink-3 hover:bg-hover hover:text-ink'}">
        <Icon class="size-[19px]" />
      </button>
    {/snippet}
  </Tip>
{/snippet}

<div class="grid h-dvh grid-cols-[60px_minmax(0,1fr)] max-sm:grid-cols-1 max-sm:grid-rows-[52px_minmax(0,1fr)]">
  <nav class="flex flex-col items-center gap-1.5 border-r border-line bg-panel py-3.5 max-sm:flex-row max-sm:border-r-0 max-sm:border-b max-sm:px-3 max-sm:py-0">
    <Tip text="Memories" side="right">
      {#snippet children(props)}
        <button {...props} aria-label="Memories" aria-current={app.page === "memories" ? "page" : undefined} class="mb-3.5 rounded-[9px] max-sm:mr-auto max-sm:mb-0"
          onclick={() => { if (app.page === "memories") app.close(); else app.go("memories"); }}>
          <span class="sm:hidden"><Brand size={28} /></span><span class="max-sm:hidden"><Brand name={false} size={32} /></span>
        </button>
      {/snippet}
    </Tip>
    {@render railButton("insights", "Insights", ChartColumn)}
    <div class="flex-1 max-sm:hidden"></div>
    {@render railButton("settings", "Settings", Settings2)}
  </nav>

  {#if app.page === "memories"}
    <!-- the list is 372, 400 or 440px wide by window size, until its edge is dragged (--list-w);
         whatever the width, the open memory keeps at least 420px -->
    <div class="grid min-h-0 grid-cols-1 lg:grid-cols-[min(var(--list-w,372px),calc(100%_-_420px))_minmax(0,1fr)] xl:grid-cols-[min(var(--list-w,400px),calc(100%_-_420px))_minmax(0,1fr)] 2xl:grid-cols-[min(var(--list-w,440px),calc(100%_-_420px))_minmax(0,1fr)]"
      style:--list-w={app.listWidth ? `${app.listWidth}px` : undefined}>
      <section bind:this={listPane} class="relative flex min-h-0 flex-col bg-panel lg:border-r lg:border-line {reading ? 'max-lg:hidden' : ''}">
        <ResizeHandle pane={listPane} />
        <div class="flex items-center justify-between gap-3 px-4 pt-3.5 pb-2.5">
          <h1 class="text-[15px] font-semibold">Memories <span class="ml-1 font-normal text-ink-3 tabular-nums">{app.M.length}</span></h1>
          <Button variant="primary" size="sm" onclick={() => app.startNew()} title="New memory (n)"><Plus />New</Button>
        </div>
        <div class="border-b border-line px-4 pb-3"><MemoriesTools /></div>
        <div class="min-h-0 flex-1 overflow-y-auto"><MemoryList /></div>
        {#if app.unpushed}<div class="border-t border-line px-4 py-2"><Unpushed /></div>{/if}
      </section>
      <section class="min-h-0 overflow-y-auto {reading ? '' : 'max-lg:hidden'}">
        <div class="mx-auto max-w-[780px] px-10 pt-4 pb-16 max-lg:px-6 max-sm:px-4">
          {#if reading}
            <button class="mb-3 inline-flex items-center gap-1.5 text-[13px] text-ink-3 hover:text-ink lg:hidden" onclick={() => app.close()}><ArrowLeft class="size-4" />All memories</button>
          {/if}
          {#if app.mode !== "view" || app.open}<MemoryPanel />{:else}<p class="pt-24 text-center text-ink-3">Pick a memory to read it here.</p>{/if}
        </div>
      </section>
    </div>
  {:else}
    <section class="min-h-0 overflow-y-auto">
      <header class="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-line bg-bg/90 px-8 backdrop-blur max-sm:h-12 max-sm:px-4">
        <h1 class="flex-1 text-[15px] font-semibold">{TITLES[app.page]}</h1>
        <Unpushed />
      </header>
      <div class="mx-auto max-w-[1180px] px-8 pt-6 pb-16 max-sm:px-4 max-sm:pt-4">{#if app.page === "insights"}<InsightsPage />{:else}<SettingsPage />{/if}</div>
    </section>
  {/if}
</div>
