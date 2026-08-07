<script setup lang="ts">
import { computed } from 'vue'

import type { AccuracyStat } from '@/api/fixtures'
import type { ResultsHitKey } from '@/utils/resultsPageState'

const props = defineProps<{
  label: string
  stat?: AccuracyStat
  color: string
  filterKey?: ResultsHitKey
  active?: boolean
}>()

const emit = defineEmits<{
  filterHit: [key: ResultsHitKey]
}>()

const hasValue = computed(
  () => !!props.stat && props.stat.total > 0 && props.stat.rate != null,
)

const percent = computed(() =>
  hasValue.value ? `${(props.stat!.rate! * 100).toFixed(0)}%` : '—',
)
</script>

<template>
  <n-statistic class="accuracy-statistic" :label="label" tabular-nums>
    <template v-if="hasValue">
      <span :style="{ color }">{{ percent }}</span>
      <span>（</span>
      <n-button
        v-if="filterKey"
        text
        size="tiny"
        class="hits-btn"
        :class="{ active }"
        :style="{ color }"
        :aria-label="active ? '取消命中筛选' : '只看该维度命中场次'"
        @click.stop="emit('filterHit', filterKey)"
      >
        {{ stat!.hits }}
      </n-button>
      <span v-else :style="{ color }">{{ stat!.hits }}</span>
      <span>/{{ stat!.total }}）</span>
    </template>
    <span v-else>{{ percent }}</span>
  </n-statistic>
</template>

<style scoped>
.accuracy-statistic {
  min-width: 0;
}

.accuracy-statistic :deep(.n-statistic-value__content) {
  display: inline-flex;
  align-items: baseline;
  flex-wrap: nowrap;
  font-size: 20px;
  line-height: 1.15;
  white-space: nowrap;
}

.hits-btn {
  vertical-align: baseline;
  height: auto;
  padding: 0;
  font: inherit;
  font-variant-numeric: tabular-nums;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.hits-btn.active {
  font-weight: 700;
}
</style>
