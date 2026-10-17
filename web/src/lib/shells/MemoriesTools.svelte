<script lang="ts">
  import FilterBar from "../components/FilterBar.svelte";
  import SearchBox from "../components/SearchBox.svelte";
</script>

<div class="grid grid-cols-[minmax(0,1fr)] gap-3">
  <SearchBox />
  <FilterBar />
</div>
