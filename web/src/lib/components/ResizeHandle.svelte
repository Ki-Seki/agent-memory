<script lang="ts">
  // The line between the list and the open memory: drag it, or focus it and use the arrow keys.
  // Double-click puts the width back to the one for the window size.
  import { app } from "$lib/store.svelte";

  let { pane }: { pane: HTMLElement | undefined } = $props();
  const MIN = 280, READ_MIN = 420, STEP = 16;
  let dragging = $state(false);

  const max = () => Math.max(MIN, Math.min(720, (pane?.parentElement?.clientWidth ?? 1200) - READ_MIN));
  const current = () => pane?.getBoundingClientRect().width ?? 360;
  const set = (w: number) => app.setListWidth(Math.round(Math.min(max(), Math.max(MIN, w))));

  function down(e: PointerEvent) {
    if (e.button !== 0 || !pane) return;
    e.preventDefault();
    try { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); } catch { /* a pointer the browser no longer tracks */ }
    dragging = true;
  }
  function move(e: PointerEvent) {
    if (dragging && pane) set(e.clientX - pane.getBoundingClientRect().left);
  }
  function up() { dragging = false; }
  function key(e: KeyboardEvent) {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); set(current() + (e.key === "ArrowRight" ? STEP : -STEP)); }
    else if (e.key === "Home") { e.preventDefault(); set(MIN); }
    else if (e.key === "End") { e.preventDefault(); set(max()); }
  }
</script>

<svelte:body class:select-none={dragging} class:cursor-col-resize={dragging} />

<!-- a focusable separator is the ARIA window-splitter pattern; Svelte counts separators as static -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions, a11y_no_noninteractive_tabindex -->
<div role="separator" aria-orientation="vertical" aria-label="Resize the list" tabindex="0"
  aria-valuemin={MIN} aria-valuemax={max()} aria-valuenow={Math.round(current())}
  title="Drag to resize; double-click to reset"
  onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={up} onlostpointercapture={up} onkeydown={key} ondblclick={() => app.setListWidth(null)}
  class="group absolute top-0 right-0 bottom-0 z-10 w-2.5 translate-x-1/2 cursor-col-resize outline-none max-lg:hidden">
  <span class="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 transition-colors {dragging ? 'bg-accent' : 'bg-transparent group-hover:bg-accent/60 group-focus-visible:bg-accent'}"></span>
</div>
