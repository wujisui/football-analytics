<script setup lang="ts">
import { computed } from 'vue'

import type { AccuracyStat } from '@/api/fixtures'

const props = withDefaults(
  defineProps<{
    label: string
    stat?: AccuracyStat
    color: string
    /** Bind click on the hit count (left of `/`). */
    hitFilterable?: boolean
    hitActive?: boolean
  }>(),
  {
    hitFilterable: false,
    hitActive: false,
  },
)

const emit = defineEmits<{
  filterHits: []
}>()

const hasValue = computed(
  () => !!props.stat && props.stat.total > 0 && props.stat.rate != null,
)

const percent = computed(() =>
  hasValue.value ? `${(props.stat!.rate! * 100).toFixed(0)}%` : '—',
)

const tooltipText = computed(() =>
  props.hitActive ? '取消命中筛选' : '只看该维度命中场次',
)

function onHitsClick(event: MouseEvent) {
  if (!props.hitFilterable || !hasValue.value) return
  event.preventDefault()
  event.stopPropagation()
  emit('filterHits')
}
</script>

<template>
  <n-statistic class="accuracy-statistic" :label="label" tabular-nums>
    <template v-if="hasValue">
      <span :style="{ color }">{{ percent }}</span>
      <span>（</span>
      <n-tooltip v-if="hitFilterable" placement="top">
        <template #trigger>
          <n-button
            text
            size="tiny"
            class="hits-btn"
            :class="{ active: hitActive }"
            :style="{ color }"
            :aria-label="tooltipText"
            @click="onHitsClick"
          >
            {{ stat!.hits }}
          </n-button>
        </template>
        {{ tooltipText }}
      </n-tooltip>
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
  flex-wrap: wrap;
  font-size: 24px;
  line-height: 1.2;
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
