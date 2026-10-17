<script lang="ts">
  import { Switch } from "bits-ui";
  let { checked, onchange, label, disabled = false }: { checked: boolean; onchange: (v: boolean) => void; label: string; disabled?: boolean } = $props();
</script>

<Switch.Root {checked} onCheckedChange={onchange} aria-label={label} {disabled}
  class="inline-flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition-colors disabled:opacity-50 data-[state=checked]:bg-accent data-[state=unchecked]:bg-line">
  <Switch.Thumb class="block size-4 rounded-full bg-white shadow-sm transition-transform data-[state=checked]:translate-x-4" />
</Switch.Root>
