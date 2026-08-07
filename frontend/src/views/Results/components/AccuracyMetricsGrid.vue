<script setup lang="ts">
import type { AccuracyStat } from '@/api/fixtures'
import AccuracyStatistic from '@/views/Results/components/AccuracyStatistic.vue'
import { ACCURACY_COLOR_BY_HIT_KEY } from '@/utils/accuracyColors'
import {
  RESULTS_HIT_OPTIONS,
  type ResultsHitKey,
} from '@/utils/resultsPageState'

type AccuracyMetrics = Partial<Record<ResultsHitKey, AccuracyStat>>

withDefaults(
  defineProps<{
    metrics?: AccuracyMetrics | null
    filterable?: boolean
    activeHitKey?: ResultsHitKey | null
  }>(),
  {
    filterable: false,
    activeHitKey: null,
  },
)

const emit = defineEmits<{
  filterHit: [key: ResultsHitKey]
}>()
</script>

<template>
  <n-grid :cols="2" :x-gap="8" :y-gap="8" class="accuracy-metrics-grid">
    <n-gi v-for="opt in RESULTS_HIT_OPTIONS" :key="opt.key">
      <AccuracyStatistic
        :label="opt.label"
        :stat="metrics?.[opt.key]"
        :color="ACCURACY_COLOR_BY_HIT_KEY[opt.key]"
        :filter-key="filterable ? opt.key : undefined"
        :active="activeHitKey === opt.key"
        @filter-hit="emit('filterHit', $event)"
      />
    </n-gi>
  </n-grid>
</template>

<style scoped>
.accuracy-metrics-grid :deep(.n-grid-item) {
  min-width: 0;
}
</style>
