<script lang="ts">
  import Check from "@lucide/svelte/icons/check";
  import Copy from "@lucide/svelte/icons/copy";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import X from "@lucide/svelte/icons/x";
  import { api } from "$lib/api";
  import ArrowUpCircle from "@lucide/svelte/icons/circle-arrow-up";
  import { plural, since } from "$lib/format";
  import { app, type Theme } from "$lib/store.svelte";
  import type { Check as HealthCheck, Settings, Sync, UpdateResult } from "$lib/types";
  import type { Snippet } from "svelte";
  import Button from "../ui/Button.svelte";
  import Segmented from "../ui/Segmented.svelte";
  import Toggle from "../ui/Toggle.svelte";

  let s = $state<Settings | null>(null);
  let checks = $state<HealthCheck[] | null>(null);
  let word = $state("");
  let syncing = $state(false);
  let checking = $state(false);
  let lookingUp = $state(false);
  let failed = $state<UpdateResult | null>(null);

  async function load() { s = await api<Settings>("/api/settings"); }
  async function runChecks() { checking = true; try { checks = (await api<{ checks: HealthCheck[] }>("/api/doctor")).checks; } finally { checking = false; } }
  $effect(() => { load(); runChecks(); });

  async function saveWords(words: string[]) {
    try { s = await api<Settings>("/api/settings", { keyword_stopwords: words }); await app.reload(); app.toast("Keywords updated"); }
    catch (e) { app.toast((e as Error).message, { error: true }); }
  }
  function addWord() { const w = word.trim().toLowerCase(); if (!w || !s) return; word = ""; if (!s.keywordStopwords.includes(w)) saveWords([...s.keywordStopwords, w]); }
  async function syncNow() {
    syncing = true;
    try { const r = await api<{ ok: boolean; sync: Sync }>("/api/sync", {}); await app.reload(); await load(); app.toast(r.ok ? "Synced" : "Sync failed; see .cache/agent-memory.log in the data repository", { error: !r.ok }); }
    catch (e) { app.toast((e as Error).message, { error: true }); }
    finally { syncing = false; }
  }
  async function checkNow() { lookingUp = true; failed = null; try { await app.refreshUpdate(true); } finally { lookingUp = false; } }
  async function updateNow() { failed = null; const r = await app.runUpdate(); if (!r.ok) failed = r; }
  async function copy(text: string) { try { await navigator.clipboard.writeText(text); app.toast("Copied"); } catch { prompt("Copy:", text); } }

  const group = "rounded-card border border-line bg-surface px-5 pt-4 pb-1 max-sm:px-4";
  const h2 = "mb-1 text-[13px] font-semibold text-ink-2";
  const u = $derived(app.update);
  const failing = $derived(checks?.filter((c) => !c.ok).length ?? 0);
</script>

<!-- a setting: its name and help on the left, the control on the right; `below` puts a long value under the name instead -->
{#snippet row(label: string, help: string | undefined, control: Snippet, below = false)}
  <div class="grid grid-cols-1 items-center gap-3 border-t border-line-soft py-3.5 first-of-type:border-t-0 {below ? '' : 'sm:grid-cols-[minmax(220px,1fr)_minmax(0,auto)] sm:gap-6'}">
    <div><div class="text-sm font-medium">{label}</div>{#if help}<div class="mt-0.5 text-[12.5px] text-ink-3">{help}</div>{/if}</div>
    <div class="min-w-0 {below ? '' : 'sm:max-w-[440px] sm:justify-self-end'}">{@render control()}</div>
  </div>
{/snippet}

<div class="grid max-w-3xl gap-6 max-sm:gap-4">
  <section class={group}>
    <h2 class={h2}>Appearance</h2>
    {#snippet theme()}<Segmented label="Theme" value={app.theme} onchange={(v) => app.setTheme(v as Theme)} options={[{ value: "system", label: "System" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} />{/snippet}
    {@render row("Theme", "Follow the system, or pick one.", theme)}
  </section>

  <section class={group}>
    <h2 class={h2}>Updates</h2>
    {#snippet version()}
      {#if u?.available && u.oneClick}
        <Button variant="primary" size="sm" onclick={updateNow} disabled={!!app.updating}>
          {#if app.updating}<RefreshCw class="animate-spin" />{app.updating === "restarting" ? "Restarting…" : "Updating…"}{:else}<ArrowUpCircle />Update to {u.latest}{/if}
        </Button>
      {:else if u?.available}
        <button class="inline-flex max-w-full items-center gap-2 rounded-md bg-chip px-2 py-1 text-left font-mono text-[12.5px] text-ink-2 hover:text-ink" onclick={() => copy(u.command)} title="Copy"><span class="break-all">{u.command}</span><Copy class="size-3.5 shrink-0" /></button>
      {:else}
        <Button size="sm" onclick={checkNow} disabled={lookingUp}><RefreshCw class={lookingUp ? "animate-spin" : ""} />Check now</Button>
      {/if}
    {/snippet}
    {@render row(
      `agent-memory ${u?.current ?? s?.version ?? ""}`,
      !u ? "Checking for updates…"
        : u.available ? `Version ${u.latest} is out.${u.oneClick ? " Updating also refreshes the hooks and restarts this page." : u.method === "dev" ? " This is a working copy; in it, run:" : " Update with:"}`
        : u.latest ? `Up to date${u.checked ? `, checked ${since(u.checked)}` : ""}.` : u.auto ? "Could not reach PyPI to check." : "Automatic checks are off.",
      version,
    )}
    {#if failed}
      <div class="mb-3 rounded-ctl bg-bad/10 px-3 py-2.5 text-[13px]">
        <div class="font-medium text-bad">{failed.error}</div>
        {#if failed.log}<pre class="mt-2 max-h-40 overflow-auto font-mono text-xs whitespace-pre-wrap text-ink-2">{failed.log}</pre>{/if}
      </div>
    {/if}
    {#snippet auto()}<Toggle label="Check for updates automatically" checked={u?.auto ?? true} onchange={(v) => app.setAutoUpdate(v)} />{/snippet}
    {@render row("Check automatically", "Once a day this page asks PyPI for the latest version; only the package name is sent.", auto)}
  </section>

  <section class={group}>
    <h2 class={h2}>Data repository</h2>
    {#snippet where()}<code class="block rounded-ctl bg-chip px-3 py-2 font-mono text-[12.5px] leading-relaxed break-all text-ink-2">{s?.dataDir ?? app.data?.dataDir}</code>{/snippet}
    {@render row("Location", "Every memory is one Markdown file in this git repository.", where, true)}
    {#snippet remote()}{#if s?.remote}<code class="rounded-md bg-chip px-2 py-1 font-mono text-[12.5px] text-ink-2">{s.remote}</code>{:else}<span class="text-[13px] text-ink-3">None, so memories stay on this machine</span>{/if}{/snippet}
    {@render row("Remote", undefined, remote)}
    {#snippet sync()}
      <div class="flex items-center gap-3">
        {#if s?.remote}
          {#if app.unpushed}<span class="inline-flex items-center gap-1.5 text-[13px] text-warn"><i class="size-[7px] rounded-full bg-warn"></i>{plural(app.unpushed, "change")} not pushed</span>
          {:else}<span class="inline-flex items-center gap-1.5 text-[13px] text-ink-2"><i class="size-[7px] rounded-full bg-ok"></i>Up to date</span>{/if}
        {/if}
        <Button size="sm" onclick={syncNow} disabled={syncing || !s?.remote}><RefreshCw class={syncing ? "animate-spin" : ""} />Sync now</Button>
      </div>
    {/snippet}
    {@render row("Sync", "Hooks commit and push after every turn; this pulls and pushes now.", sync)}
  </section>

  <section class={group}>
    <h2 class={h2}>Keywords</h2>
    {#snippet words()}
      <div class="flex w-full max-w-[360px] flex-wrap items-center gap-1.5 rounded-ctl border border-line bg-surface p-1 focus-within:border-accent">
        {#each s?.keywordStopwords ?? [] as w (w)}
          <span class="inline-flex h-6 items-center gap-0.5 rounded-md bg-chip pr-0.5 pl-2 text-[12.5px]">{w}<button class="grid size-5 place-items-center rounded text-ink-3 hover:text-ink" aria-label="Remove {w}" onclick={() => saveWords(s!.keywordStopwords.filter((x) => x !== w))}><X class="size-3" /></button></span>
        {/each}
        <input bind:value={word} placeholder="Add a word" class="h-6 min-w-24 flex-1 bg-transparent px-1.5 text-[13px] outline-none placeholder:text-ink-3" onkeydown={(e) => { if (e.key === "Enter") { e.preventDefault(); addWord(); } }} />
      </div>
    {/snippet}
    {@render row("Never use as keywords", "Words such as your own name, kept out of keyword chips and filters.", words)}
  </section>

  <section class={group}>
    <h2 class={h2}>Search by meaning</h2>
    {#snippet model()}
      <div class="grid justify-items-start gap-1.5 sm:justify-items-end">
        {#if s?.model.ready}<span class="inline-flex items-center gap-1.5 text-[13px] text-ink-2"><i class="size-[7px] rounded-full bg-ok"></i>Ready{s.semantic ? "" : " (restart mem ui to use it)"}</span>
        {:else}<span class="inline-flex items-center gap-1.5 text-[13px] text-ink-2"><i class="size-[7px] rounded-full bg-ink-3"></i>Not downloaded</span>
          <button class="inline-flex items-center gap-2 rounded-md bg-chip px-2 py-1 font-mono text-[12.5px] text-ink-2 hover:text-ink" onclick={() => copy(s!.model.fetch)} title="Copy">{s?.model.fetch}<Copy class="size-3.5" /></button>{/if}
      </div>
    {/snippet}
    {@render row("Local model", `${s?.model.name ?? "Embedding model"}, on the CPU; ${s?.model.size ?? ""}. Finds memories close in meaning, across Chinese and English.`, model)}
  </section>

  <section class={group}>
    <div class="flex items-center justify-between">
      <h2 class={h2}>Health</h2>
      {#if checks}<span class="text-xs {failing ? 'text-warn' : 'text-ink-3'}">{failing ? `${plural(failing, "check")} failing` : "All checks pass"}</span>{/if}
    </div>
    <ul>
      {#each checks ?? [] as c (c.text)}
        <li class="flex items-start gap-2.5 border-t border-line-soft py-2.5 text-[13.5px] first:border-t-0">
          {#if c.ok}<Check class="mt-0.5 size-4 shrink-0 text-ok" />{:else}<TriangleAlert class="mt-0.5 size-4 shrink-0 text-warn" />{/if}
          <span class={c.ok ? "" : "text-ink"}>{c.text}</span>
        </li>
      {/each}
    </ul>
    <div class="flex items-center justify-between border-t border-line-soft py-3">
      <span class="text-xs text-ink-3">The same checks as <code class="font-mono">mem doctor</code></span>
      <Button size="sm" onclick={runChecks} disabled={checking}>Run checks again</Button>
    </div>
  </section>
</div>
