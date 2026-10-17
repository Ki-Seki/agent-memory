<script lang="ts">
  import Inline from "./Inline.svelte";
  import { app } from "$lib/store.svelte";
  import type { Inline as Node } from "$lib/markdown";
  let { nodes }: { nodes: Node[] } = $props();
</script>

{#each nodes as n, i (i)}{#if n.k === "text"}{n.v}{:else if n.k === "code"}<code>{n.v}</code>{:else if n.k === "strong"}<strong><Inline nodes={n.c} /></strong>{:else if n.k === "em"}<em><Inline nodes={n.c} /></em>{:else if n.k === "wiki"}{#if app.byName.has(n.name)}<a href="#/memories/{encodeURIComponent(app.byName.get(n.name)!.id)}" onclick={(e) => { e.preventDefault(); app.openByName(n.name); }}>{n.name}</a>{:else}<span title="No memory has this name">[[{n.name}]]</span>{/if}{:else if n.k === "link"}<a href={n.href} target="_blank" rel="noopener noreferrer">{n.text}</a>{/if}{/each}
