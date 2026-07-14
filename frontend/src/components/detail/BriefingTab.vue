<script setup lang="ts">
import { computed } from 'vue'
import type { DataTableColumns } from 'naive-ui'

import type { PrematchPackage } from '@/api/types'

type ComparisonRow = {
  key: string
  label: string
  home?: string | null
  away?: string | null
}

const props = defineProps<{
  homeTeamName: string
  awayTeamName: string
  homeTeamId?: number | null
  awayTeamId?: number | null
  pkg: PrematchPackage | null
}>()

const briefing = computed(() => props.pkg?.briefing ?? null)
const available = computed(() => !!briefing.value?.available)

const homeName = computed(() => props.homeTeamName || '—')
const awayName = computed(() => props.awayTeamName || '—')

const percent = computed(() => briefing.value?.percent ?? {})
const goals = computed(() => briefing.value?.goals ?? {})
const comparison = computed(() => briefing.value?.comparison ?? [])

type GoalLineParsed = {
  display: string
  over: boolean | null
  line: string | null
}

/** Keep +/- as shown; localize Over/Under wording from the API. */
function parseGoalField(raw: string | null | undefined): GoalLineParsed | null {
  if (raw == null || String(raw).trim() === '') return null
  const s = String(raw).trim()
  const lower = s.toLowerCase()
  if (lower.startsWith('over')) {
    const line = s.slice(4).trim().replace(',', '.') || null
    return {
      display: line ? `大球 ${line}` : '大球',
      over: true,
      line,
    }
  }
  if (lower.startsWith('under')) {
    const line = s.slice(5).trim().replace(',', '.') || null
    return {
      display: line ? `小球 ${line}` : '小球',
      over: false,
      line,
    }
  }
  const signed = s.match(/^([+-])\s*(\d+(?:[.,]\d+)?)$/)
  if (signed) {
    const line = signed[2].replace(',', '.')
    return {
      display: `${signed[1]}${line}`,
      over: signed[1] === '+',
      line,
    }
  }
  return { display: s, over: null, line: null }
}

function tipForTotal(parsed: GoalLineParsed): string {
  if (parsed.over != null && parsed.line) {
    return parsed.over
      ? `总进球大于 ${parsed.line}`
      : `总进球小于 ${parsed.line}`
  }
  return '全场总进球（主客相加）的大小倾向'
}

function tipForSide(side: '主' | '客', parsed: GoalLineParsed): string {
  const who = side === '主' ? '主队' : '客队'
  if (parsed.over != null && parsed.line) {
    return `${side} ${parsed.display} 表示${who}本场进球${parsed.over ? '大于' : '小于'} ${parsed.line}`
  }
  return `${side} ${parsed.display} 表示${who}本场进球`
}

const underOverParsed = computed(() => parseGoalField(briefing.value?.under_over))
const goalsHomeParsed = computed(() => parseGoalField(goals.value.home))
const goalsAwayParsed = computed(() => parseGoalField(goals.value.away))

const underOverDisplay = computed(() => underOverParsed.value?.display ?? '')
const underOverTip = computed(() =>
  underOverParsed.value ? tipForTotal(underOverParsed.value) : '',
)

const goalsDisplay = computed(() => {
  const parts: string[] = []
  if (goalsHomeParsed.value) parts.push(`主 ${goalsHomeParsed.value.display}`)
  if (goalsAwayParsed.value) parts.push(`客 ${goalsAwayParsed.value.display}`)
  return parts.join(' / ')
})

const goalsTip = computed(() => {
  const lines: string[] = []
  if (goalsHomeParsed.value) lines.push(tipForSide('主', goalsHomeParsed.value))
  if (goalsAwayParsed.value) lines.push(tipForSide('客', goalsAwayParsed.value))
  return lines.join('\n')
})

const comparisonColumns = computed<DataTableColumns<ComparisonRow>>(() => [
  { title: '维度', key: 'label', width: 100 },
  { title: homeName.value, key: 'home' },
  { title: awayName.value, key: 'away' },
])
</script>

<template>
  <div class="briefing-tab">
    <n-empty
      v-if="!available"
      description="官方暂无赛前简报（部分联赛无 coverage.predictions）"
    />

    <template v-else>
      <n-alert type="info" :bordered="false" class="source-note">
        来源：API-Sports 官方 /predictions，与「我的预测」本地模型无关
      </n-alert>

      <n-card
        v-if="briefing?.advice"
        size="small"
        title="建议"
        :bordered="false"
        class="block"
      >
        <n-text>{{ briefing.advice }}</n-text>
      </n-card>

      <n-descriptions
        label-placement="left"
        :column="1"
        size="small"
        class="block"
      >
        <n-descriptions-item v-if="briefing?.winner?.name" label="倾向胜方">
          {{ briefing.winner.name }}
          <n-text v-if="briefing.winner.comment" depth="3">
            （{{ briefing.winner.comment }}）
          </n-text>
        </n-descriptions-item>
        <n-descriptions-item
          v-if="briefing?.win_or_draw != null"
          label="胜或平"
        >
          {{ briefing.win_or_draw ? '是' : '否' }}
        </n-descriptions-item>
        <n-descriptions-item v-if="underOverDisplay" label="大小球">
          <n-space :size="4" align="center" :wrap="false">
            <span>{{ underOverDisplay }}</span>
            <n-tooltip v-if="underOverTip" trigger="hover" placement="bottom">
              <template #trigger>
                <n-button
                  quaternary
                  circle
                  size="tiny"
                  tertiary
                  aria-label="大小球说明"
                >
                  ?
                </n-button>
              </template>
              {{ underOverTip }}
            </n-tooltip>
          </n-space>
        </n-descriptions-item>
        <n-descriptions-item v-if="goalsDisplay" label="预期进球">
          <n-space :size="4" align="center" :wrap="false">
            <span>{{ goalsDisplay }}</span>
            <n-tooltip v-if="goalsTip" trigger="hover" placement="bottom">
              <template #trigger>
                <n-button
                  quaternary
                  circle
                  tertiary
                  size="tiny"
                  aria-label="预期进球说明"
                >
                  ?
                </n-button>
              </template>
              <n-space vertical :size="4">
                <div v-for="(line, idx) in goalsTip.split('\n')" :key="idx">
                  {{ line }}
                </div>
              </n-space>
            </n-tooltip>
          </n-space>
        </n-descriptions-item>
      </n-descriptions>

      <div v-if="percent.home || percent.draw || percent.away" class="percents block">
        <n-statistic label="主胜" :value="percent.home || '—'" />
        <n-statistic label="平局" :value="percent.draw || '—'" />
        <n-statistic label="客胜" :value="percent.away || '—'" />
      </div>

      <n-data-table
        v-if="comparison.length"
        size="small"
        :bordered="false"
        :single-line="false"
        :columns="comparisonColumns"
        :data="comparison"
        :pagination="false"
        class="block"
      />
    </template>
  </div>
</template>

<style scoped>
.briefing-tab {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.source-note {
  background: var(--fa-bg-muted, transparent);
}

.block {
  background: var(--fa-bg-elevated);
}

.percents {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 8px 0;
}

@media (max-width: 767px) {
  .percents {
    gap: 8px;
  }
}
</style>
