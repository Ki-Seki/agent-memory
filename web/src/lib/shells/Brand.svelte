<script lang="ts">
  // The mark: a lowercase m for mem, its last stroke ending in a stored point.
  let { name = true, size = 26 }: { name?: boolean; size?: number } = $props();
</script>

<span class="inline-flex items-center gap-2.5 text-[15px] font-semibold tracking-[-0.01em]">
  <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" class="shrink-0">
    <rect width="24" height="24" rx="7" fill="#5b5bd6" />
    <path d="M6.5 17v-5.75a2.75 2.75 0 0 1 5.5 0V17M12 11.25a2.75 2.75 0 0 1 5.5 0V14" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    <circle cx="17.5" cy="17.2" r="1.6" fill="#fff" />
  </svg>
  {#if name}agent-memory{/if}
</span>
