<script setup lang="ts">
import { computed } from 'vue'

import type { AccuracyStat } from '@/api/fixtures'

const props = defineProps<{
  label: string
  stat?: AccuracyStat
  color: string
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
      <span :style="{ color }">{{ stat!.hits }}</span>
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
</style>
