<script lang="ts">
  import Blocks from "./Blocks.svelte";
  import Inline from "./Inline.svelte";
  import type { Block } from "$lib/markdown";
  let { blocks }: { blocks: Block[] } = $props();
</script>

{#each blocks as b, i (i)}
  {#if b.k === "p"}<p><Inline nodes={b.c} /></p>
  {:else if b.k === "h"}<svelte:element this={`h${b.level}`}><Inline nodes={b.c} /></svelte:element>
  {:else if b.k === "hr"}<hr class="border-line" />
  {:else if b.k === "pre"}<pre><code>{b.v}</code></pre>
  {:else if b.k === "quote"}<blockquote><Blocks blocks={b.c} /></blockquote>
  {:else if b.k === "list"}
    <svelte:element this={b.ordered ? "ol" : "ul"}>
      {#each b.items as item, j (j)}<li><Inline nodes={item.c} />{#if item.sub.length}<Blocks blocks={item.sub} />{/if}</li>{/each}
    </svelte:element>
  {:else if b.k === "table"}
    <div class="overflow-x-auto"><table class="text-[13px]">
      <thead><tr>{#each b.head as c, j (j)}<th class="border border-line px-2 py-1 text-left"><Inline nodes={c} /></th>{/each}</tr></thead>
      <tbody>{#each b.rows as r, j (j)}<tr>{#each r as c, k (k)}<td class="border border-line px-2 py-1 align-top"><Inline nodes={c} /></td>{/each}</tr>{/each}</tbody>
    </table></div>
  {/if}
{/each}
