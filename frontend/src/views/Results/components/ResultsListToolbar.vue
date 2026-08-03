<script setup lang="ts">
import { StatsChartOutline } from '@vicons/ionicons5'

import PageToolbarSearch from '@/components/PageToolbarSearch.vue'
import ResultsFilterTrigger from '@/views/Results/components/ResultsFilterTrigger.vue'
import type { ResultsHitKey } from '@/utils/resultsPageState'

withDefaults(
  defineProps<{
    selectedHitKeys: ResultsHitKey[]
    filterActive: boolean
    /** Phone: open 当日统计 modal from the list toolbar. */
    showDayStats?: boolean
  }>(),
  { showDayStats: false },
)

const teamSearch = defineModel<string>('teamSearch', { required: true })

const emit = defineEmits<{
  confirmFilter: [hitKeys: ResultsHitKey[]]
  openDayStats: []
}>()
</script>

<template>
  <n-flex :wrap="false" align="center" :size="8" style="width: 100%; min-width: 0;">
    <PageToolbarSearch
      v-model="teamSearch"
      style="flex: 1; width: auto; min-width: 0; max-width: none;"
    />
    <n-button
      v-if="showDayStats"
      size="small"
      type="primary"
      secondary
      aria-label="当日统计"
      @click="emit('openDayStats')"
    >
      <template #icon>
        <n-icon :component="StatsChartOutline" />
      </template>
      当日统计
    </n-button>
    <ResultsFilterTrigger
      :selected-hit-keys="selectedHitKeys"
      :filter-active="filterActive"
      @confirm="emit('confirmFilter', $event)"
    />
  </n-flex>
</template>
