<script lang="ts">
  import { app } from "$lib/store.svelte";
  import { fly } from "svelte/transition";
</script>

<div class="pointer-events-none fixed bottom-6 left-1/2 z-50 grid -translate-x-1/2 gap-2" aria-live="polite">
  {#each app.toasts as t (t.id)}
    <div transition:fly={{ y: 8, duration: 160 }} class="pointer-events-auto flex items-center gap-4 rounded-[10px] px-4 py-2.5 text-[13px] shadow-pop {t.error ? 'bg-bad text-white' : 'bg-ink text-bg'}">
      <span>{t.text}</span>
      {#if t.undo}
        <button class="font-semibold underline underline-offset-2" onclick={() => { app.dismiss(t.id); app.undo(t.undo!); }}>Undo</button>
      {/if}
    </div>
  {/each}
</div>
