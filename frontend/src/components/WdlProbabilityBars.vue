<script setup lang="ts">
import { toPercent } from '@/utils/format'

withDefaults(
  defineProps<{
    /** 胜 / 平 / 负 三列；`value` 是 0..1 的概率。 */
    items: { key: string; label: string; value: number }[]
    /** `card` = 独立预测卡：更细的条 + 更大的百分比。 */
    variant?: 'list' | 'card'
  }>(),
  { variant: 'list' },
)
</script>

<template>
  <div class="prob-row" :class="variant">
    <div v-for="item in items" :key="item.key" class="prob-item">
      <span class="prob-head">
        <span>{{ item.label }}</span>
        <strong>{{ toPercent(item.value) }}</strong>
      </span>
      <n-progress
        type="line"
        :percentage="Math.round(item.value * 100)"
        :show-indicator="false"
        :height="variant === 'card' ? 6 : 8"
      />
    </div>
  </div>
</template>

<style scoped>
.prob-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.prob-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.prob-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px;
  font-size: 11px;
  line-height: 1.2;
  color: var(--fa-text-faint);
  user-select: none;
}

.prob-head strong {
  color: var(--fa-text-strong);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.prob-row.card .prob-item {
  gap: 4px;
}

.prob-row.card .prob-head {
  gap: 2px;
}

.prob-row.card .prob-head strong {
  font-size: 14px;
  font-weight: 700;
}
</style>
