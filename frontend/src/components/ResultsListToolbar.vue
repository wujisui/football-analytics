<script setup lang="ts">
import PageToolbarSearch from '@/components/PageToolbarSearch.vue'
import ResultsFilterTrigger from '@/components/ResultsFilterTrigger.vue'
import type { ResultsHitKey } from '@/utils/resultsPageState'

defineProps<{
  selectedHitKeys: ResultsHitKey[]
  filterActive: boolean
}>()

const teamSearch = defineModel<string>('teamSearch', { required: true })

const emit = defineEmits<{
  confirmFilter: [hitKeys: ResultsHitKey[]]
}>()
</script>

<template>
  <div class="results-list-toolbar">
    <PageToolbarSearch v-model="teamSearch" />
    <ResultsFilterTrigger
      :selected-hit-keys="selectedHitKeys"
      :filter-active="filterActive"
      @confirm="emit('confirmFilter', $event)"
    />
  </div>
</template>

<style scoped>
.results-list-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

.results-list-toolbar :deep(.fa-toolbar-search) {
  flex: 1;
  width: auto;
  min-width: 0;
  max-width: none;
}
</style>
