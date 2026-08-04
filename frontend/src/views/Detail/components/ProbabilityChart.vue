<script setup lang="ts">
import { PieChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'

import type { ProbabilitiesResponse } from '@/api/types'
import { WDL_COLORS } from '@/theme/wdlColors'

use([CanvasRenderer, PieChart, TooltipComponent])

const props = withDefaults(
  defineProps<{
    probabilities: ProbabilitiesResponse
    compact?: boolean
  }>(),
  { compact: false },
)

function cssVar(name: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

const option = computed(() => {
  const muted = cssVar('--fa-text-secondary', '#999')
  return {
    animation: true,
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {d}%',
    },
    // Side copy (主胜/平局/客胜) is the legend — colors match 统计 tab WDL.
    series: [
      {
        name: '胜平负',
        type: 'pie',
        radius: props.compact ? ['48%', '72%'] : ['42%', '68%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: true,
        data: [
          {
            name: '主胜',
            value: Number(((props.probabilities.home_win_prob ?? 0) * 100).toFixed(1)),
            itemStyle: { color: WDL_COLORS.win },
          },
          {
            name: '平局',
            value: Number(((props.probabilities.draw_prob ?? 0) * 100).toFixed(1)),
            itemStyle: { color: WDL_COLORS.draw },
          },
          {
            name: '客胜',
            value: Number(((props.probabilities.away_win_prob ?? 0) * 100).toFixed(1)),
            itemStyle: { color: WDL_COLORS.loss },
          },
        ],
        label: {
          formatter: '{d}%',
          color: muted,
          fontSize: props.compact ? 11 : 12,
        },
        labelLine: {
          length: props.compact ? 10 : 14,
          length2: props.compact ? 8 : 10,
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.45)',
          },
        },
      },
    ],
  }
})
</script>

<template>
  <VChart class="chart" :class="{ compact }" :option="option" autoresize />
</template>

<style scoped>
.chart {
  width: 100%;
  height: 360px;
}

.chart.compact {
  height: 220px;
}
</style>
