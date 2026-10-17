<script lang="ts">
  import X from "@lucide/svelte/icons/x";
  import { TYPE_HELP, TYPES } from "$lib/filters";
  import { app } from "$lib/store.svelte";
  import type { MemoryType } from "$lib/types";
  import TypeDot from "./TypeDot.svelte";
  import Button from "./ui/Button.svelte";
  import IconButton from "./ui/IconButton.svelte";
  import Segmented from "./ui/Segmented.svelte";
  import SelectMenu from "./ui/SelectMenu.svelte";

  const d = $derived(app.draft!);
  let error = $state("");
  let saving = $state(false);
  const isNew = $derived(app.mode === "new");
  const OTHER = "__folder";
  const placeItems = $derived([
    ...(d.place && !app.places.some((p) => p.key === d.place) ? [{ value: d.place, label: d.place }] : []),
    ...app.places.map((p) => ({ value: p.key, label: p.key })),
    { value: OTHER, label: "Another folder…" },
  ]);
  const field = "w-full rounded-ctl border border-line bg-surface px-3 py-2 text-ink outline-none placeholder:text-ink-3 focus:border-accent focus:ring-3 focus:ring-accent-soft";
  const label = "mb-1.5 flex items-baseline justify-between text-xs font-semibold text-ink-3";

  export async function submit() {
    saving = true;
    error = await app.save();
    saving = false;
  }
  let descEl: HTMLTextAreaElement | undefined = $state();
  $effect(() => { if (isNew) descEl?.focus(); });
</script>

<form class="min-w-0" onsubmit={(e) => { e.preventDefault(); submit(); }} data-memory-form>
  <div class="flex h-8 items-center gap-1">
    <span class="mr-auto truncate font-mono text-xs text-ink-3">{isNew ? "New memory" : `Editing · memories/${app.open?.rel}`}</span>
    <IconButton label="Cancel (Esc)" onclick={() => app.cancelEdit()}><X /></IconButton>
  </div>

  <div class="mt-4 grid gap-5">
    <label class="block">
      <span class={label}>Description <span class="font-normal tabular-nums {d.description.length > 150 ? 'text-bad' : ''}">{d.description.length} / 150</span></span>
      <textarea bind:this={descEl} bind:value={d.description} rows="2" placeholder="One line: what should an agent know?" class="{field} resize-y text-[15px] font-medium"></textarea>
    </label>

    <div>
      <div class={label}>Type <span class="font-normal">{TYPE_HELP[d.type]}</span></div>
      <Segmented label="Type" value={d.type} onchange={(v) => (d.type = v as MemoryType)} options={TYPES.map((t) => ({ value: t, label: t }))}>
        {#snippet lead(v)}<TypeDot type={v as MemoryType} />{/snippet}
      </Segmented>
    </div>

    <div>
      <div class={label}>Loads</div>
      <div class="flex flex-wrap items-center gap-3">
        <Segmented label="Loads" value={d.scope} onchange={(v) => (d.scope = v as "global" | "here")} options={[{ value: "global", label: "Everywhere" }, { value: "here", label: "One place" }]} />
        {#if d.scope === "here"}
          <SelectMenu label="Place" class="w-72 max-w-full" placeholder="Choose a place…" value={d.pathMode ? OTHER : d.place} items={placeItems}
            onchange={(v) => { d.pathMode = v === OTHER; d.place = v === OTHER ? "" : v; }} />
        {/if}
      </div>
      {#if d.scope === "here" && d.pathMode}
        <input type="text" bind:value={d.path} placeholder="~/repos/project" class="{field} mt-2 font-mono text-[13px]" aria-label="Folder path" />
      {/if}
    </div>

    <label class="block">
      <span class={label}>Memory <span class="font-normal">Markdown</span></span>
      <textarea bind:value={d.body} spellcheck="false" placeholder={"The fact itself.\n\n**Why:** …\n\n**How to apply:** …"} class="{field} min-h-72 resize-y font-mono text-[13px] leading-relaxed"></textarea>
    </label>
  </div>

  <div class="sticky bottom-0 mt-5 flex items-center gap-2 border-t border-line bg-inherit py-3">
    <span class="flex-1 text-[13px] text-bad" role="alert">{error}</span>
    <Button onclick={() => app.cancelEdit()}>Cancel</Button>
    <Button variant="primary" type="submit" disabled={saving} title="⌘S">{isNew ? "Add memory" : "Save"}</Button>
  </div>
</form>
