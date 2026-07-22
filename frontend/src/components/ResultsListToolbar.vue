<script setup lang="ts">
import PageToolbarSearch from '@/components/PageToolbarSearch.vue'
import ResultsFilterTrigger from '@/components/ResultsFilterTrigger.vue'
import type { ResultsFilterConfirm, ResultsHitKey } from '@/utils/resultsPageState'

defineProps<{
  selectedHitKeys: ResultsHitKey[]
  hideWithoutPrediction: boolean
  filterActive: boolean
}>()

const teamSearch = defineModel<string>('teamSearch', { required: true })

const emit = defineEmits<{
  confirmFilter: [payload: ResultsFilterConfirm]
}>()
</script>

<template>
  <div class="results-list-toolbar">
    <PageToolbarSearch v-model="teamSearch" />
    <ResultsFilterTrigger
      :selected-hit-keys="selectedHitKeys"
      :hide-without-prediction="hideWithoutPrediction"
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
