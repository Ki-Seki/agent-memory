<script lang="ts">
  import { Tooltip } from "bits-ui";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import SelectionBar from "$lib/components/SelectionBar.svelte";
  import Toasts from "$lib/components/Toasts.svelte";
  import Shell from "$lib/shells/Shell.svelte";
  import { app } from "$lib/store.svelte";

  app.start();

  $effect(() => {
    const root = document.documentElement;
    if (app.theme === "system") delete root.dataset.theme;
    else root.dataset.theme = app.theme;
  });
  $effect(() => {
    const words = { memories: "Memories", insights: "Insights", settings: "Settings" };
    document.title = `${app.open && app.page === "memories" ? app.open.description : words[app.page]} · agent-memory`;
  });

  function onkeydown(e: KeyboardEvent) {
    const el = document.activeElement as HTMLElement | null;
    const typing = !!el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable) && (el as HTMLInputElement).type !== "checkbox";
    if (app.asking || document.querySelector("[role=dialog], [role=alertdialog], [data-popover-content], [data-menu-content]")) return;  // a dialog or menu handles its own keys
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s" && app.mode !== "view") {
      e.preventDefault();
      document.querySelector<HTMLFormElement>("[data-memory-form]")?.requestSubmit();
      return;
    }
    if (e.key === "Escape") {
      if (typing) { el!.blur(); return; }
      if (app.mode !== "view") return void app.cancelEdit();
      if (app.openId && !app.wide.current) return void app.close();  // narrow: back to the list
      if (app.picked.size) return app.picked.clear();
      if (app.q) return app.search("");
      return;
    }
    if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key;
    if (k === "/") { e.preventDefault(); if (app.page !== "memories") app.go("memories"); queueMicrotask(() => document.getElementById("q")?.focus()); }
    else if (k === "n") { e.preventDefault(); app.startNew(); }
    else if (app.page !== "memories" || app.mode !== "view") return;
    else if (k === "e" && app.open) { e.preventDefault(); app.startEdit(); }
    else if (k === "j" || k === "ArrowDown") { e.preventDefault(); app.moveCursor(1); }
    else if (k === "k" || k === "ArrowUp") { e.preventDefault(); app.moveCursor(-1); }
    else if (k === "Enter") { e.preventDefault(); app.openCursor(); }
    else if (k === "x" && app.rows[app.cursor]) { e.preventDefault(); app.togglePick(app.rows[app.cursor].id); }
  }
</script>

<svelte:window {onkeydown} />

<Tooltip.Provider delayDuration={400}>
  {#if app.bootError}
    <div class="grid h-screen place-items-center p-6 text-center text-ink-3">{app.bootError}</div>
  {:else if !app.data}
    <div class="grid h-screen place-items-center text-ink-3">Loading memories…</div>
  {:else}
    <Shell />
  {/if}
  <SelectionBar />
  <Toasts />
  <ConfirmDialog />
</Tooltip.Provider>
