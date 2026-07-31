<script setup lang="ts">
import { PieChart } from 'echarts/charts'
import { LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'

import type { ProbabilitiesResponse } from '@/api/types'

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent])

const props = withDefaults(
  defineProps<{
    probabilities: ProbabilitiesResponse
    compact?: boolean
  }>(),
  { compact: false },
)

const option = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {d}%',
  },
  legend: {
    bottom: 0,
    show: !props.compact,
  },
  series: [
    {
      type: 'pie',
      radius: props.compact ? ['35%', '62%'] : ['40%', '70%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 6,
        borderColor: '#fff',
        borderWidth: 2,
      },
      label: {
        formatter: props.compact ? '{d}%' : '{b}\n{d}%',
        fontSize: props.compact ? 11 : 12,
      },
      data: [
        {
          name: '主胜',
          value: Number(((props.probabilities.home_win_prob ?? 0) * 100).toFixed(1)),
        },
        {
          name: '平局',
          value: Number(((props.probabilities.draw_prob ?? 0) * 100).toFixed(1)),
        },
        {
          name: '客胜',
          value: Number(((props.probabilities.away_win_prob ?? 0) * 100).toFixed(1)),
        },
      ],
    },
  ],
}))
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
  height: 200px;
}
</style>
