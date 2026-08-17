<script lang="ts">
/** Chart window ending at today; step 5, max 30; ``0`` = full series. */
export const DEFAULT_CHART_WINDOW_DAYS = 30

export const CHART_WINDOW_OPTIONS = [
  {label: '5天', value: 5},
  {label: '10天', value: 10},
  {label: '15天', value: 15},
  {label: '20天', value: 20},
  {label: '25天', value: 25},
  {label: '30天', value: 30},
  {label: '全部', value: 0},
]
</script>

<script setup lang="ts">
import {RefreshOutline} from '@vicons/ionicons5'

withDefaults(
    defineProps<{
      /** Select width; phone toolbar is slightly tighter. */
      selectWidth?: string
    }>(),
    {selectWidth: '84px'},
)

const windowDays = defineModel<number>({default: DEFAULT_CHART_WINDOW_DAYS})

function resetWindow() {
  windowDays.value = DEFAULT_CHART_WINDOW_DAYS
}
</script>

<template>
  <n-flex :wrap="false" align="center" :size="6" class="chart-window-controls">
    <n-select
        v-model:value="windowDays"
        size="tiny"
        :options="CHART_WINDOW_OPTIONS"
        :consistent-menu-width="false"
        :style="{ width: selectWidth }"
    />
    <n-tooltip trigger="hover">
      <template #trigger>
        <n-button
            size="tiny"
            text
            type="primary"
            aria-label="重置走势图范围"
            @click="resetWindow"
        >
          <template #icon>
            <n-icon :component="RefreshOutline" :size="18"/>
          </template>
        </n-button>
      </template>
      重置走势图30天范围
    </n-tooltip>
  </n-flex>
</template>

<style scoped>
.chart-window-controls {
  flex-shrink: 0;
}
</style>
