<script setup lang="ts">
import type { AccuracyStat } from '@/api/fixtures'
import AccuracyStatistic from '@/views/Results/components/AccuracyStatistic.vue'
import { ACCURACY_COLORS } from '@/utils/accuracyColors'
import {
  RESULTS_HIT_OPTIONS,
  type ResultsHitKey,
} from '@/utils/resultsPageState'

type AccuracyMetrics = Partial<Record<ResultsHitKey, AccuracyStat>>

withDefaults(
  defineProps<{
    metrics?: AccuracyMetrics | null
    hitFilterable?: boolean
    activeHitKey?: ResultsHitKey | null
  }>(),
  {
    hitFilterable: false,
    activeHitKey: null,
  },
)

const emit = defineEmits<{
  filterHits: [key: ResultsHitKey]
}>()

const COLOR_BY_KEY: Record<ResultsHitKey, string> = {
  result: ACCURACY_COLORS.result,
  single_result: ACCURACY_COLORS.singleResult,
  score: ACCURACY_COLORS.score,
  ou: ACCURACY_COLORS.ou,
  btts: ACCURACY_COLORS.btts,
  handicap: ACCURACY_COLORS.handicap,
}
</script>

<template>
  <n-grid :cols="2" :x-gap="8" :y-gap="8" class="accuracy-metrics-grid">
    <n-gi v-for="opt in RESULTS_HIT_OPTIONS" :key="opt.key">
      <AccuracyStatistic
        :label="opt.label"
        :stat="metrics?.[opt.key]"
        :color="COLOR_BY_KEY[opt.key]"
        :hit-filterable="hitFilterable"
        :hit-active="activeHitKey === opt.key"
        @filter-hits="emit('filterHits', opt.key)"
      />
    </n-gi>
  </n-grid>
</template>

<style scoped>
.accuracy-metrics-grid :deep(.n-grid-item) {
  min-width: 0;
}
</style>
