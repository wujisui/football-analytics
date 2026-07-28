<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'

import type { AccuracyDayPoint } from '@/api/fixtures'
import { ACCURACY_COLORS } from '@/utils/accuracyColors'

use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
])

/** Enable pan/slider when more than this many sample days. */
const SCROLL_DAY_THRESHOLD = 14
/** Initial visible window size (days) when scrolling is on. */
const INITIAL_VIEW_DAYS = 21

const props = defineProps<{
  series: AccuracyDayPoint[]
  /** Currently focused results day (YYYY-MM-DD); shown as a guide line. */
  selectedDay?: string | null
}>()

const emit = defineEmits<{
  selectDay: [day: string]
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
  const header = `${dateLabel} ${matchCount}场 · 点击查看当天赛果`
  const lines = params.map((item) => {
    const value = item.value == null ? '—' : `${item.value}%`
    return `${item.marker ?? ''}${item.seriesName ?? ''}: ${value}`
  })
  return [header, ...lines].join('<br/>')
}

function onChartClick(params: {
  componentType?: string
  dataIndex?: number
}) {
  if (params.componentType === 'markLine') return
  const idx = params.dataIndex
  if (idx == null || idx < 0) return
  const day = props.series[idx]?.date
  if (day) emit('selectDay', day)
}

const option = computed(() => {
  const n = props.series.length
  const scrollable = n > SCROLL_DAY_THRESHOLD
  const dates = props.series.map((p) => p.date.slice(5)) // MM-DD
  const viewStart = scrollable
    ? Math.max(0, 100 - (INITIAL_VIEW_DAYS / n) * 100)
    : 0
  const selectedIndex = props.selectedDay
    ? props.series.findIndex((p) => p.date === props.selectedDay)
    : -1

  const selectedMarkLine =
    selectedIndex >= 0
      ? {
          silent: true,
          symbol: 'none' as const,
          animation: false,
          label: { show: false },
          lineStyle: {
            type: 'dashed' as const,
            color: 'rgba(255, 255, 255, 0.45)',
            width: 1,
          },
          data: [{ xAxis: selectedIndex }],
        }
      : undefined

  function line(
    name: string,
    color: string,
    values: Array<number | null>,
    withMark = false,
  ) {
    return {
      name,
      type: 'line' as const,
      smooth: true,
      itemStyle: { color },
      lineStyle: { color },
      showSymbol: true,
      symbolSize: 6,
      connectNulls: false,
      cursor: 'pointer',
      data: values,
      ...(withMark && selectedMarkLine ? { markLine: selectedMarkLine } : {}),
    }
  }

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
      bottom: scrollable ? 28 : 4,
      containLabel: true,
    },
    dataZoom: scrollable
      ? [
          {
            type: 'inside',
            xAxisIndex: 0,
            filterMode: 'none',
            start: viewStart,
            end: 100,
            zoomOnMouseWheel: false,
            moveOnMouseMove: true,
            moveOnMouseWheel: true,
          },
          {
            type: 'slider',
            xAxisIndex: 0,
            height: 18,
            bottom: 2,
            start: viewStart,
            end: 100,
            brushSelect: false,
            borderColor: 'transparent',
            fillerColor: 'rgba(24, 160, 88, 0.18)',
            handleSize: '80%',
            showDetail: false,
          },
        ]
      : [],
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
      line(
        '胜平负',
        ACCURACY_COLORS.result,
        props.series.map((p) => toPct(p.result_rate)),
        true,
      ),
      line(
        '让球胜平负',
        ACCURACY_COLORS.handicap,
        props.series.map((p) => toPct(p.handicap_rate)),
      ),
      line(
        '比分',
        ACCURACY_COLORS.score,
        props.series.map((p) => toPct(p.score_rate)),
      ),
      line(
        '大小球',
        ACCURACY_COLORS.ou,
        props.series.map((p) => toPct(p.ou_rate)),
      ),
      line(
        '双方进球',
        ACCURACY_COLORS.btts,
        props.series.map((p) => toPct(p.btts_rate)),
      ),
    ],
  }
})
</script>

<template>
  <VChart
    class="accuracy-chart"
    :option="option"
    autoresize
    @click="onChartClick"
  />
</template>

<style scoped>
.accuracy-chart {
  width: 100%;
  height: 100%;
  min-height: 160px;
  cursor: pointer;
}
</style>
