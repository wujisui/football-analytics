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
import { ACCURACY_COLORS } from '@/utils/accuracyColors'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps<{
  series: AccuracyDayPoint[]
}>()

function toPct(rate: number | null | undefined): number | null {
  if (rate == null) return null
  return Number((rate * 100).toFixed(1))
}

function formatAxisTooltip(
  params: Array<{
    axisValue?: string
    dataIndex?: number
    marker?: string
    seriesName?: string
    value?: number | null
  }>,
): string {
  if (!params.length) return ''
  const idx = params[0].dataIndex ?? 0
  const point = props.series[idx]
  const dateLabel = point?.date ?? String(params[0].axisValue ?? '')
  const matchCount = point?.fixtures_finished ?? 0
  const header = `${dateLabel} ${matchCount}场`
  const lines = params.map((item) => {
    const value = item.value == null ? '—' : `${item.value}%`
    return `${item.marker ?? ''}${item.seriesName ?? ''}: ${value}`
  })
  return [header, ...lines].join('<br/>')
}

const option = computed(() => {
  const dates = props.series.map((p) => p.date.slice(5)) // MM-DD
  return {
    tooltip: {
      trigger: 'axis',
      formatter: formatAxisTooltip,
    },
    legend: {
      top: 4,
      left: 'center',
      data: ['胜平负', '让球胜平负', '比分', '大小球', '双方进球'],
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
        itemStyle: { color: ACCURACY_COLORS.result },
        lineStyle: { color: ACCURACY_COLORS.result },
        showSymbol: props.series.length <= 14,
        connectNulls: false,
        data: props.series.map((p) => toPct(p.result_rate)),
      },
      {
        name: '让球胜平负',
        type: 'line',
        smooth: true,
        itemStyle: { color: ACCURACY_COLORS.handicap },
        lineStyle: { color: ACCURACY_COLORS.handicap },
        showSymbol: props.series.length <= 14,
        connectNulls: false,
        data: props.series.map((p) => toPct(p.handicap_rate)),
      },
      {
        name: '比分',
        type: 'line',
        smooth: true,
        itemStyle: { color: ACCURACY_COLORS.score },
        lineStyle: { color: ACCURACY_COLORS.score },
        showSymbol: props.series.length <= 14,
        connectNulls: false,
        data: props.series.map((p) => toPct(p.score_rate)),
      },
      {
        name: '大小球',
        type: 'line',
        smooth: true,
        itemStyle: { color: ACCURACY_COLORS.ou },
        lineStyle: { color: ACCURACY_COLORS.ou },
        showSymbol: props.series.length <= 14,
        connectNulls: false,
        data: props.series.map((p) => toPct(p.ou_rate)),
      },
      {
        name: '双方进球',
        type: 'line',
        smooth: true,
        itemStyle: { color: ACCURACY_COLORS.btts },
        lineStyle: { color: ACCURACY_COLORS.btts },
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
