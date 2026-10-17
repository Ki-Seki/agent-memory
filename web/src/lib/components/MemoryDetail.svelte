<script lang="ts">
  // One memory: what it says first, then where it came from, the rest of its frontmatter, and similar memories.
  import Copy from "@lucide/svelte/icons/copy";
  import Folder from "@lucide/svelte/icons/folder";
  import Globe from "@lucide/svelte/icons/globe";
  import Pencil from "@lucide/svelte/icons/pencil";
  import Trash2 from "@lucide/svelte/icons/trash-2";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import { Tabs } from "bits-ui";
  import { TYPE_HELP } from "$lib/filters";
  import { longDay } from "$lib/format";
  import { parse } from "$lib/markdown";
  import { app } from "$lib/store.svelte";
  import type { Memory } from "$lib/types";
  import Blocks from "./Blocks.svelte";
  import TypeDot from "./TypeDot.svelte";
  import IconButton from "./ui/IconButton.svelte";
  import Tip from "./ui/Tip.svelte";

  let { m }: { m: Memory } = $props();
  let tab = $state("memory");
  const blocks = $derived(parse(m.body));
  const source = $derived((m.meta.source ?? {}) as Record<string, unknown>);
  const SOURCE: [string, string][] = [["tool", "Written by"], ["session_name", "Session"], ["session_id", "Session id"], ["model", "Model"], ["host", "Host"], ["cwd", "Folder"], ["git_remote", "Repository"], ["git_branch", "Branch"], ["git_commit", "Commit"]];
  const provenance = $derived(SOURCE.map(([k, label]): [string, string] => [label, String(source[k] ?? "")]).filter(([, v]) => v));
  const details = $derived(Object.entries(m.meta).filter(([k]) => !["source", "description", "type", "scope"].includes(k)).map(([k, v]): [string, string] => [k, Array.isArray(v) ? v.join(", ") : String(v)]));
  const similar = $derived(m.similar.filter((s) => s.s > 0.05).slice(0, 5).map((s) => ({ m: app.M[s.i], s: s.s })).filter((x) => x.m));
  const show = (text: string) => text.replace(/\*\*([^*]+?):?\*\*/g, "“$1”");

  async function copyPath() {
    try { await navigator.clipboard.writeText(m.path); app.toast("Path copied"); } catch { prompt("Copy:", m.path); }
  }
  $effect(() => { void m.id; tab = "memory"; });
</script>

<article class="min-w-0">
  <div class="flex h-8 items-center gap-1">
    <span class="mr-auto min-w-0 truncate font-mono text-xs text-ink-3" title={m.path}>memories/{m.rel}</span>
    <IconButton label="Copy file path" onclick={copyPath}><Copy /></IconButton>
    <IconButton label="Edit (e)" onclick={() => app.startEdit()}><Pencil /></IconButton>
    <IconButton label="Delete" onclick={() => app.remove([m.id])}><Trash2 /></IconButton>
  </div>

  <h1 class="mt-3 text-[21px] leading-snug font-semibold tracking-[-0.015em] max-sm:text-[19px]">{m.description}</h1>

  <div class="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-ink-2">
    <Tip text={TYPE_HELP[m.type]}>
      {#snippet children(props)}<span {...props}><TypeDot type={m.type} label /></span>{/snippet}
    </Tip>
    <span class="text-ink-3">·</span>
    <span class="inline-flex min-w-0 items-center gap-1.5">
      {#if m.scope === "global"}<Globe class="size-3.5 text-ink-3" />Loads everywhere{:else}<Folder class="size-3.5 text-ink-3" /><span class="truncate">{m.place}</span>{/if}
    </span>
    <span class="text-ink-3">·</span>
    <span>Added {longDay(m.created)}</span>
    {#if m.updated}<span class="text-ink-3">· changed {longDay(m.updated)}</span>{/if}
  </div>

  {#if m.keywords.length}
    <div class="mt-3 flex flex-wrap gap-1.5">
      {#each m.keywords as k (k.k)}
        <button class="rounded-md px-2 text-xs leading-[22px] {app.filters.kw.includes(k.k) ? 'bg-ink text-bg' : 'bg-chip text-ink-2 hover:bg-accent-soft hover:text-ink'}"
          title={app.filters.kw.includes(k.k) ? `Stop filtering by ${k.t}` : `Only memories that mention ${k.t}`} onclick={() => app.toggle("kw", k.k)}>{k.t}</button>
      {/each}
    </div>
  {/if}

  {#if m.issues.length}
    <div class="mt-4 flex gap-2.5 rounded-ctl bg-warn/10 px-3 py-2.5 text-[13px] text-ink-2">
      <TriangleAlert class="mt-0.5 size-4 shrink-0 text-warn" />
      <div><div class="font-medium text-ink">Differs from the format in PROTOCOL.md</div>
        <ul class="mt-1 list-disc pl-4">{#each m.issues as issue (issue)}<li>{show(issue)}</li>{/each}</ul></div>
    </div>
  {/if}

  <Tabs.Root bind:value={tab} class="mt-5">
    <Tabs.List class="flex gap-5 border-b border-line">
      {#each [["memory", "Memory"], ["file", "File"]] as [v, label] (v)}
        <Tabs.Trigger value={v} class="-mb-px border-b-2 border-transparent pb-2 text-[13px] text-ink-3 hover:text-ink data-[state=active]:border-ink data-[state=active]:font-semibold data-[state=active]:text-ink">{label}</Tabs.Trigger>
      {/each}
    </Tabs.List>
    <Tabs.Content value="memory" class="pt-5 outline-none">
      <div class="md"><Blocks {blocks} /></div>

      {#if provenance.length}
        <section class="mt-9">
          <h2 class="mb-2.5 text-xs font-semibold text-ink-3">Provenance</h2>
          <dl class="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-5 gap-y-1.5 text-[13px]">
            {#each provenance as [k, v] (k)}<dt class="text-ink-3">{k}</dt><dd class="font-mono text-[12.5px] break-all text-ink-2">{v}</dd>{/each}
          </dl>
        </section>
      {/if}
      <section class="mt-8">
        <h2 class="mb-2.5 text-xs font-semibold text-ink-3">Details</h2>
        <dl class="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-5 gap-y-1.5 text-[13px]">
          {#each details as [k, v] (k)}<dt class="text-ink-3">{k}</dt><dd class="font-mono text-[12.5px] break-all text-ink-2">{v}</dd>{/each}
        </dl>
      </section>
      {#if similar.length}
        <section class="mt-8">
          <h2 class="mb-1 text-xs font-semibold text-ink-3">Similar</h2>
          {#each similar as x (x.m.id)}
            <button class="flex w-full items-baseline gap-3 border-t border-line-soft py-2 text-left text-[13.5px] hover:[&>span:first-child]:underline hover:[&>span:first-child]:underline-offset-3" onclick={() => app.openMemory(x.m.id)}>
              <span class="flex-1">{x.m.description}</span><span class="text-xs text-ink-3 tabular-nums">{Math.round(x.s * 100)}%</span>
            </button>
          {/each}
        </section>
      {/if}
    </Tabs.Content>
    <Tabs.Content value="file" class="pt-5 outline-none">
      <pre class="overflow-x-auto rounded-ctl bg-code px-4 py-3 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-ink-2">{m.raw}</pre>
    </Tabs.Content>
  </Tabs.Root>
</article>
