<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'

import type { AccuracyDayPoint, AccuracyStat } from '@/api/fixtures'
import { ACCURACY_COLORS } from '@/utils/accuracyColors'
import { addCalendarDays, scheduleTodayDate } from '@/utils/homeDateStrip'

use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
])

type PlayKey = 'result' | 'handicap' | 'score' | 'ou' | 'btts'

/** Line order matches ``seriesIndex``; labels/colors mirror 当日统计 cards. */
const PLAY_LINES: ReadonlyArray<{ name: string; color: string; key: PlayKey }> = [
  { name: '推荐结果', color: ACCURACY_COLORS.result, key: 'result' },
  { name: '让球胜平负', color: ACCURACY_COLORS.handicap, key: 'handicap' },
  { name: '比分', color: ACCURACY_COLORS.score, key: 'score' },
  { name: '大小球', color: ACCURACY_COLORS.ou, key: 'ou' },
  { name: '双方进球', color: ACCURACY_COLORS.btts, key: 'btts' },
]

const props = withDefaults(
  defineProps<{
    series: AccuracyDayPoint[]
    /** Currently focused results day (YYYY-MM-DD); shown as a guide line. */
    selectedDay?: string | null
    /** Visible window ending at today (calendar days). */
    windowDays?: number
  }>(),
  {
    selectedDay: null,
    windowDays: 30,
  },
)

const emit = defineEmits<{
  selectDay: [day: string]
}>()

/** ``windowDays <= 0`` → full series（全部）; otherwise last N days ending today. */
const viewSeries = computed(() => {
  if (props.windowDays <= 0) return props.series
  const end = scheduleTodayDate()
  const days = Math.max(1, props.windowDays)
  const start = addCalendarDays(end, -(days - 1))
  return props.series.filter((p) => p.date >= start && p.date <= end)
})

function toPct(rate: number | null | undefined): number | null {
  if (rate == null) return null
  return Number((rate * 100).toFixed(1))
}

/** ``60%（3/5）``; each play type has its own sample size. */
function formatStat(stat: AccuracyStat | undefined, pct: number | null): string {
  if (!stat || stat.total <= 0 || pct == null) return '—（无样本）'
  return `${pct}%（${stat.hits}/${stat.total}）`
}

function formatAxisTooltip(
  params: Array<{
    axisValue?: string
    dataIndex?: number
    marker?: string
    seriesIndex?: number
    seriesName?: string
    value?: number | null
  }>,
): string {
  if (!params.length) return ''
  const idx = params[0].dataIndex ?? 0
  const point = viewSeries.value[idx]
  const dateLabel = point?.date ?? String(params[0].axisValue ?? '')
  const header = `${dateLabel} 已预测 ${point?.fixtures_with_prediction ?? 0} 场`
  const lines = params.map((item) => {
    const play = PLAY_LINES[item.seriesIndex ?? -1]
    const stat = play && point ? point[play.key] : undefined
    const label = item.seriesName ?? play?.name ?? ''
    return `${item.marker ?? ''}${label}: ${formatStat(stat, item.value ?? null)}`
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
  const day = viewSeries.value[idx]?.date
  if (day) emit('selectDay', day)
}

const option = computed(() => {
  const points = viewSeries.value
  const dates = points.map((p) => p.date.slice(5)) // MM-DD
  const selectedIndex = props.selectedDay
    ? points.findIndex((p) => p.date === props.selectedDay)
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

  const lines = PLAY_LINES.map((play, index) => ({
    name: play.name,
    type: 'line' as const,
    // Straight segments are cheaper than bezier smooth on mobile GPUs.
    smooth: false,
    itemStyle: { color: play.color },
    lineStyle: { color: play.color },
    showSymbol: true,
    symbolSize: 6,
    connectNulls: false,
    cursor: 'pointer',
    data: points.map((p) => toPct(p[play.key]?.rate)),
    ...(index === 0 && selectedMarkLine ? { markLine: selectedMarkLine } : {}),
  }))

  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      formatter: formatAxisTooltip,
    },
    legend: {
      top: 4,
      left: 'center',
      itemWidth: 16,
      itemHeight: 8,
      itemGap: 12,
      textStyle: { fontSize: 11 },
      data: PLAY_LINES.map((play) => play.name),
    },
    grid: {
      left: 8,
      right: 12,
      // Compact legend fits one row on phones; keep a small clear gap below it.
      top: 38,
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
    series: lines,
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
