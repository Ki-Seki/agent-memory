<script lang="ts">
  import { AlertDialog } from "bits-ui";
  import { app } from "$lib/store.svelte";
  import { button } from "./ui/Button.svelte";

  const a = $derived(app.asking);
</script>

<AlertDialog.Root open={!!a} onOpenChange={(o) => { if (!o) app.answer(false); }}>
  <AlertDialog.Portal>
    <AlertDialog.Overlay class="fixed inset-0 z-50 bg-black/30 animate-in fade-in-0" />
    <AlertDialog.Content class="fixed top-1/2 left-1/2 z-50 w-[min(440px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-card border border-line bg-surface p-5 shadow-pop animate-in fade-in-0 zoom-in-95">
      <AlertDialog.Title class="text-[15px] font-semibold">{a?.title}</AlertDialog.Title>
      {#if a?.body}<AlertDialog.Description class="mt-2 text-[13.5px] whitespace-pre-line text-ink-2">{a.body}</AlertDialog.Description>{/if}
      <div class="mt-5 flex justify-end gap-2">
        <AlertDialog.Cancel class={button({ variant: "secondary" })}>Cancel</AlertDialog.Cancel>
        <AlertDialog.Action class={button({ variant: a?.danger ? "danger" : "primary" })} onclick={() => app.answer(true)}>{a?.action}</AlertDialog.Action>
      </div>
    </AlertDialog.Content>
  </AlertDialog.Portal>
</AlertDialog.Root>
