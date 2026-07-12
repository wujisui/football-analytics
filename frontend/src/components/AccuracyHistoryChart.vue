<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'

import type { AccuracyDayPoint } from '@/api/fixtures'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps<{
  series: AccuracyDayPoint[]
}>()

function toPct(rate: number | null | undefined): number | null {
  if (rate == null) return null
  return Number((rate * 100).toFixed(1))
}

const option = computed(() => {
  const dates = props.series.map((p) => p.date.slice(5)) // MM-DD
  return {
    color: ['#d03050', '#2080f0', '#f0a020', '#18a058'],
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: number | null) => (v == null ? '—' : `${v}%`),
    },
    legend: {
      top: 4,
      left: 'center',
      data: ['胜平负', '比分', '大小球', '双方进球'],
    },
    grid: {
      left: 8,
      right: 12,
      top: 40,
      bottom: 4,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLabel: { fontSize: 11, hideOverlap: true },
      axisTick: { alignWithLabel: true },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { formatter: '{value}%', fontSize: 11 },
      splitLine: { lineStyle: { type: 'dashed', opacity: 0.45 } },
    },
    series: [
      {
        name: '胜平负',
        type: 'line',
        smooth: true,
        showSymbol: props.series.length <= 14,
        connectNulls: false,
        data: props.series.map((p) => toPct(p.result_rate)),
      },
      {
        name: '比分',
        type: 'line',
        smooth: true,
        showSymbol: props.series.length <= 14,
        connectNulls: false,
        data: props.series.map((p) => toPct(p.score_rate)),
      },
      {
        name: '大小球',
        type: 'line',
        smooth: true,
        showSymbol: props.series.length <= 14,
        connectNulls: false,
        data: props.series.map((p) => toPct(p.ou_rate)),
      },
      {
        name: '双方进球',
        type: 'line',
        smooth: true,
        showSymbol: props.series.length <= 14,
        connectNulls: false,
        data: props.series.map((p) => toPct(p.btts_rate)),
      },
    ],
  }
})
</script>

<template>
  <VChart class="accuracy-chart" :option="option" autoresize />
</template>

<style scoped>
.accuracy-chart {
  width: 100%;
  height: 100%;
  min-height: 160px;
}
</style>
