<script setup lang="ts">
import PageToolbarSearch from '@/components/PageToolbarSearch.vue'
import ResultsFilterTrigger from '@/views/Results/components/ResultsFilterTrigger.vue'
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
  <n-flex :wrap="false" align="center" :size="8" style="width: 100%; min-width: 0;">
    <PageToolbarSearch
      v-model="teamSearch"
      style="flex: 1; width: auto; min-width: 0; max-width: none;"
    />
    <ResultsFilterTrigger
      :selected-hit-keys="selectedHitKeys"
      :filter-active="filterActive"
      @confirm="emit('confirmFilter', $event)"
    />
  </n-flex>
</template>
