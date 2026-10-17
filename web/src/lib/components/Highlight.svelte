<script lang="ts">
  import { marks } from "$lib/search";
  let { text, words }: { text: string; words: string[] } = $props();
</script>

{#each marks(text, words) as part, i (i)}{#if part.hit}<mark>{part.text}</mark>{:else}{part.text}{/if}{/each}
