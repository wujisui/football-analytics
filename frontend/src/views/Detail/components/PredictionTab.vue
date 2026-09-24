<script setup lang="ts">
import { computed, h } from 'vue'
import { NButton, NTooltip, type DataTableColumns } from 'naive-ui'

import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import DetailSectionTitle from '@/views/Detail/components/DetailSectionTitle.vue'
import PredictionResult from '@/views/Detail/components/PredictionResult.vue'
import type {
  FixtureResponse,
  FormMatch,
  OddsPackage,
  PrematchPackage,
} from '@/api/types'
import { formatLocalMonthDayMinute } from '@/utils/format'
import { useAuthSession } from '@/composables/useAuthSession'
import { hasOddsMarkets } from '@/utils/oddsDisplay'

const props = defineProps<{
  fixture: FixtureResponse
  pkg?: PrematchPackage | null
  oddsRefreshing?: boolean
  oddsRefreshBlocked?: boolean
  officialSyncBusy?: boolean
}>()
const emit = defineEmits<{ 'refresh-odds': [] }>()
const { isAdmin } = useAuthSession()

interface OddsStage {
  key: 'initial' | 'mid' | 'late' | 'current'
  title: string
  description?: string
  odds: OddsPackage
  capturedAt: string
}

/** 落槽前的候选：盘口可能整段缺失，只有中盘之后才知道采集时间。 */
type OddsStageSource = Omit<OddsStage, 'odds' | 'capturedAt'> & {
  odds?: OddsPackage | null
}

const oddsStages = computed<OddsStage[]>(() => {
  const pkg = props.fixture.analysis.package
  const sources: OddsStageSource[] = [
    {
      key: 'initial',
      title: '初盘',
      description: '首次采集的机构盘口',
      odds: pkg?.odds_opening,
    },
    {
      key: 'mid',
      title: '中盘',
      odds: pkg?.odds_mid,
    },
    {
      key: 'late',
      title: '临场',
      odds: pkg?.odds_late,
    },
    {
      key: 'current',
      title: '即时盘',
      odds: pkg?.odds,
    },
  ]
  const candidates = sources.filter(
    (stage): stage is OddsStageSource & { odds: OddsPackage } =>
      !!stage.odds && hasOddsMarkets(stage.odds),
  )

  // 同一次采集可能同时命中一个目标槽位和 current，只展示语义更靠后的阶段。
  const seen = new Set<string>()
  return candidates
    .reverse()
    .filter((stage) => {
      const capturedAt = stage.odds.scraped_at || stage.odds.captured_at || ''
      const identity = capturedAt || `${stage.key}-without-clock`
      if (seen.has(identity)) return false
      seen.add(identity)
      return true
    })
    .reverse()
    .map(stage => ({
      ...stage,
      capturedAt: stage.odds.scraped_at || stage.odds.captured_at || '',
    }))
})
const showAnyBoard = computed(() => oddsStages.value.length > 0)

const isFinished = computed(
  () => (props.fixture.status ?? '').toLowerCase() === 'finished',
)
const canRefreshOdds = computed(
  () =>
    isAdmin.value
    && props.fixture.odds_refresh_allowed === true,
)

const pkg = computed(
  () => props.pkg ?? props.fixture.analysis.package ?? null,
)

type ComparisonRow = {
  team: string
  played: number
  goalsFor: number
  avgFor: string
  goalsAgainst: number
  avgAgainst: string
}

function scoreGoals(score: string): [number, number] | null {
  const match = score.trim().match(/^(\d+)\s*[-:]\s*(\d+)$/)
  return match ? [Number(match[1]), Number(match[2])] : null
}

function average(total: number, played: number): string {
  if (!played) return '—'
  return (total / played).toFixed(1)
}

function comparisonRow(
  team: string,
  teamId: number,
  matches: FormMatch[],
): ComparisonRow {
  const recent = matches
    .map((match) => ({ match, goals: scoreGoals(match.score) }))
    .filter(
      (item): item is { match: FormMatch; goals: [number, number] } =>
        item.goals != null,
    )
    .slice(0, 5)
  let goalsFor = 0
  let goalsAgainst = 0
  for (const { match, goals } of recent) {
    if (Number(match.home_id) === teamId) {
      goalsFor += goals[0]
      goalsAgainst += goals[1]
    } else if (Number(match.away_id) === teamId) {
      goalsFor += goals[1]
      goalsAgainst += goals[0]
    }
  }
  return {
    team,
    played: recent.length,
    goalsFor,
    avgFor: average(goalsFor, recent.length),
    goalsAgainst,
    avgAgainst: average(goalsAgainst, recent.length),
  }
}

const comparisonRows = computed<ComparisonRow[]>(() => [
  comparisonRow(
    props.fixture.home_team_name || '—',
    props.fixture.home_team_id,
    pkg.value?.home_form?.matches ?? [],
  ),
  comparisonRow(
    props.fixture.away_team_name || '—',
    props.fixture.away_team_id,
    pkg.value?.away_form?.matches ?? [],
  ),
])

const comparisonColumns: DataTableColumns<ComparisonRow> = [
  {
    title: '球队',
    key: 'team',
    align: 'center',
    minWidth: 92,
    render(row) {
      return h('span', { class: 'comparison-team' }, row.team)
    },
  },
  { title: '赛', key: 'played', align: 'center', width: 42 },
  { title: '总进', key: 'goalsFor', align: 'center', width: 50 },
  { title: '均进', key: 'avgFor', align: 'center', width: 50 },
  { title: '总失', key: 'goalsAgainst', align: 'center', width: 50 },
  { title: '均失', key: 'avgAgainst', align: 'center', width: 50 },
]

type AdviceRow = { item: string; value: string }
type OfficialComparisonRow = {
  key: string
  label: string
  home?: string | null
  away?: string | null
}

function localizeGoalField(raw: string | null | undefined): string {
  if (raw == null || String(raw).trim() === '') return ''
  const s = String(raw).trim()
  const lower = s.toLowerCase()
  if (lower.startsWith('over')) {
    const line = s.slice(4).trim().replace(',', '.')
    return line ? `大球 ${line}` : '大球'
  }
  if (lower.startsWith('under')) {
    const line = s.slice(5).trim().replace(',', '.')
    return line ? `小球 ${line}` : '小球'
  }
  return s
}

const adviceRows = computed<AdviceRow[]>(() => {
  const briefing = pkg.value?.briefing
  if (!briefing?.available) return []
  const rows: AdviceRow[] = []
  if (briefing.advice) rows.push({ item: '建议', value: briefing.advice })
  if (briefing.winner?.name) {
    const comment = briefing.winner.comment ? `（${briefing.winner.comment}）` : ''
    rows.push({ item: '倾向胜方', value: `${briefing.winner.name}${comment}` })
  }
  if (briefing.win_or_draw != null) {
    rows.push({ item: '胜或平', value: briefing.win_or_draw ? '是' : '否' })
  }
  const underOver = localizeGoalField(briefing.under_over)
  if (underOver) rows.push({ item: '大小球', value: underOver })
  const goalsHome = localizeGoalField(briefing.goals?.home)
  const goalsAway = localizeGoalField(briefing.goals?.away)
  const goalsParts = [
    goalsHome ? `主 ${goalsHome}` : '',
    goalsAway ? `客 ${goalsAway}` : '',
  ].filter(Boolean)
  if (goalsParts.length) rows.push({ item: '预期进球', value: goalsParts.join(' / ') })
  if (briefing.percent?.home) rows.push({ item: '主胜', value: briefing.percent.home })
  if (briefing.percent?.draw) rows.push({ item: '平局', value: briefing.percent.draw })
  if (briefing.percent?.away) rows.push({ item: '客胜', value: briefing.percent.away })
  return rows
})

const adviceColumns: DataTableColumns<AdviceRow> = [
  { title: '项目', key: 'item', align: 'center', width: 72 },
  {
    title: '结论',
    key: 'value',
    align: 'center',
    minWidth: 120,
    render(row) {
      return h('span', { class: 'advice-value' }, row.value)
    },
  },
]

const officialComparisonRows = computed(
  () => pkg.value?.briefing?.comparison ?? [],
)

const officialComparisonColumns = computed<DataTableColumns<OfficialComparisonRow>>(
  () => [
    {
      title: '维度',
      key: 'label',
      width: 100,
      align: 'center',
      render(row) {
        if (row.key !== 'poisson_distribution') return row.label
        return h('span', { class: 'comparison-label-with-help' }, [
          row.label,
          h(
            NTooltip,
            { trigger: 'hover', placement: 'bottom' },
            {
              trigger: () =>
                h(
                  NButton,
                  {
                    quaternary: true,
                    circle: true,
                    tertiary: true,
                    size: 'tiny',
                    'aria-label': '泊松分布说明',
                  },
                  { default: () => '?' },
                ),
              default: () =>
                '依据两队历史进球与失球数据，用泊松模型估算本场进球分布。这里显示双方的相对强弱占比，不等同于上方胜平负概率。',
            },
          ),
        ])
      },
    },
    {
      title: props.fixture.home_team_name || '—',
      key: 'home',
      align: 'center',
    },
    {
      title: props.fixture.away_team_name || '—',
      key: 'away',
      align: 'center',
    },
  ],
)
</script>

<template>
  <div class="prediction-tab">
    <div v-if="showAnyBoard || canRefreshOdds" class="board-block">
      <DetailSectionTitle title="盘口" />
      <section
        v-for="stage in oddsStages"
        :key="stage.key"
        class="fa-section"
      >
        <div class="board-head">
          <div class="board-title">
            <h3 class="fa-section-title">{{ stage.title }}</h3>
            <n-text v-if="stage.description" depth="3" class="board-description">
              {{ stage.description }}
            </n-text>
          </div>
          <n-flex align="center" :size="8">
            <n-text v-if="stage.capturedAt" depth="3" class="board-time">
              {{ formatLocalMonthDayMinute(stage.capturedAt) }}
            </n-text>
            <n-button
              v-if="canRefreshOdds && stage.key === 'current'"
              size="tiny"
              secondary
              type="primary"
              :loading="oddsRefreshing"
              :disabled="oddsRefreshBlocked"
              @click="emit('refresh-odds')"
            >
              更新盘口
            </n-button>
          </n-flex>
        </div>
        <PreMatchOddsTable :odds="stage.odds" />
      </section>

      <section v-if="!showAnyBoard" class="fa-section">
        <div class="board-head">
          <n-empty description="暂无官方盘口，可手动更新本场" />
          <n-button
            size="tiny"
            secondary
            type="primary"
            :loading="oddsRefreshing"
            :disabled="oddsRefreshBlocked"
            @click="emit('refresh-odds')"
          >
            更新盘口
          </n-button>
        </div>
      </section>
    </div>

    <n-alert
      v-if="canRefreshOdds && officialSyncBusy"
      type="warning"
      :bordered="false"
    >
      后台官方同步正在执行，暂时不能单独更新本场盘口
    </n-alert>

    <PredictionResult
      :fixture="fixture"
      :is-finished="isFinished"
      :data-source="fixture.analysis.data_source"
      :analyzed-at="formatLocalMonthDayMinute(fixture.analysis.analyzed_at)"
      :handicap-market-note="fixture.analysis.handicap_market_note || ''"
    />

    <n-space vertical :size="8">
      <DetailSectionTitle title="数据对比" />
      <n-data-table
        class="compact-table"
        size="small"
        :bordered="true"
        :single-line="false"
        :pagination="false"
        :columns="comparisonColumns"
        :data="comparisonRows"
        :row-key="(row: ComparisonRow) => row.team"
      />
    </n-space>

    <n-space vertical :size="8">
      <DetailSectionTitle title="API-Sports 官方建议" />
      <n-data-table
        v-if="adviceRows.length"
        class="compact-table"
        size="small"
        :bordered="true"
        :single-line="false"
        :pagination="false"
        :columns="adviceColumns"
        :data="adviceRows"
        :row-key="(row: AdviceRow) => row.item"
      />
      <n-data-table
        v-if="officialComparisonRows.length"
        class="compact-table official-comparison-table"
        size="small"
        :bordered="false"
        :single-line="false"
        :pagination="false"
        :columns="officialComparisonColumns"
        :data="officialComparisonRows"
        :row-key="(row: OfficialComparisonRow) => row.key"
      />
      <n-empty
        v-else-if="!adviceRows.length"
        description="官方暂无赛前建议（部分联赛无 coverage.predictions）"
        size="small"
      />
    </n-space>
  </div>
</template>

<style scoped>
.prediction-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.board-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.board-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.board-title {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px 10px;
  min-width: 0;
}

.board-title .fa-section-title {
  color: var(--fa-text-secondary);
}

.board-description,
.board-time {
  font-size: 12px;
}

.compact-table :deep(.n-data-table-th),
.compact-table :deep(.n-data-table-td) {
  padding: 0;
  font-size: 12px;
  line-height: 1.8;
}

:deep(.comparison-team),
:deep(.advice-value) {
  display: block;
  overflow: hidden;
  min-width: 0;
  font-weight: 600;
}

:deep(.comparison-team) {
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.advice-value) {
  padding: 0 6px;
  font-weight: 500;
  white-space: normal;
  line-height: 1.6;
}

:deep(.comparison-label-with-help) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
</style>
