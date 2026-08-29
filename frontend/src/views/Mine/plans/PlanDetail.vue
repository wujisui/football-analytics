<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'

import { fetchFixtureScores } from '@/api/fixtures'
import { useBetPlans } from '@/composables/useBetPlans'
import FixtureMatchup from '@/components/FixtureMatchup.vue'
import {
  effectiveHandicapLine,
  foldModeLabel,
  outcomeTitle,
  selectedFixtureIds,
  type CalcOutcome,
  type CalcSelection,
} from '@/utils/betCalculator'
import { formatDate, formatLocalDateMinute, formatTime, leagueTagColor } from '@/utils/format'
import { useHandicapRuleset } from '@/composables/useHandicapRuleset'
import {
  planStatusLabel,
  planStatusTagType,
  settleBetPlan,
  type FixtureScoreSnap,
  type LegVerdict,
  type PlanSettlement,
  type SettledLeg,
} from '@/utils/betPlanSettle'

defineOptions({ name: 'BetPlanDetail' })

const props = defineProps<{
  planId: string | null
}>()

const message = useMessage()
const { getPlan, ensureLoaded } = useBetPlans()
const { ruleset } = useHandicapRuleset()

const loadingScores = ref(false)
const scores = ref<Map<number, FixtureScoreSnap>>(new Map())

const plan = computed(() => (props.planId ? getPlan(props.planId) : null))

const settlement = computed((): PlanSettlement | null => {
  const current = plan.value
  if (!current) return null
  return settleBetPlan(
    current.selections,
    current.fold,
    current.multiplier,
    scores.value,
    ruleset.value,
  )
})

/** 产品口径：全赢、赢半、输半均计入命中场次；走水单列。 */
const hitFixtureCount = computed(() => {
  const hitIds = new Set<number>()
  for (const leg of settlement.value?.legs ?? []) {
    if (
      leg.verdict === 'hit' ||
      leg.verdict === 'half_win' ||
      leg.verdict === 'half_loss'
    ) {
      hitIds.add(leg.pick.fixtureId)
    }
  }
  return hitIds.size
})

const voidFixtureCount = computed(() => {
  const verdicts = new Map<number, Set<LegVerdict>>()
  for (const leg of settlement.value?.legs ?? []) {
    const values = verdicts.get(leg.pick.fixtureId) ?? new Set<LegVerdict>()
    values.add(leg.verdict)
    verdicts.set(leg.pick.fixtureId, values)
  }
  return [...verdicts.values()].filter((values) => values.has('void')).length
})

function verdictLabel(v: LegVerdict): string {
  if (v === 'hit') return '中'
  if (v === 'half_win') return '赢半'
  if (v === 'half_loss') return '输半'
  if (v === 'miss') return '未中'
  if (v === 'void') return '走水'
  return '待定'
}

const settlementStatusTagType = computed(() => {
  return planStatusTagType(settlement.value?.status ?? 'pending')
})

const actualPrizeText = computed(() => {
  const s = settlement.value
  if (!s) return '—'
  if (s.status === 'pending') return '待结算'
  return `${s.actualPrize ?? 0} 元`
})

const actualPrizeTextType = computed(() =>
  settlement.value?.status === 'won' ? 'error' : undefined,
)

function verdictType(v: LegVerdict): 'error' | 'warning' | 'default' {
  if (v === 'hit' || v === 'half_win') return 'error'
  if (v === 'void') return 'warning'
  return 'default'
}

function verdictDisabled(v: LegVerdict): boolean {
  return v === 'miss' || v === 'half_loss'
}

const OUTCOME_ORDER: CalcOutcome[] = [
  'home',
  'draw',
  'away',
  'over',
  'under',
  'yes',
  'no',
]

type FixtureLegGroup = {
  fixtureId: number
  leagueId: number
  leagueName: string
  homeName: string
  awayName: string
  kickoff: string
  /** Frozen kickoff no longer matches the fixture: officially moved to this label. */
  rescheduledLabel: string | null
  scoreText: string | null
  rows: {
    key: string
    playLabel: string
    picks: { key: string; label: string; verdict: LegVerdict }[]
  }[]
}

/** 让球标签跟当前口径走：方案存的是原始盘口，竞彩显示实际结算的整数盘。 */
function playLabelForRuleset(pick: CalcSelection): string {
  if (pick.market !== 'ah') return pick.playLabel
  const line = effectiveHandicapLine(pick.line, ruleset.value)
  return line ? `让球 ${line}` : pick.playLabel
}

/** Group legs by fixture (matchup shown once); combine same-market dual picks. */
const legGroups = computed((): FixtureLegGroup[] => {
  const legs = settlement.value?.legs ?? []
  const byFixture = new Map<number, SettledLeg[]>()
  for (const leg of legs) {
    const list = byFixture.get(leg.pick.fixtureId) ?? []
    list.push(leg)
    byFixture.set(leg.pick.fixtureId, list)
  }
  return [...byFixture.values()].map((fixtureLegs) => {
    const first = fixtureLegs[0].pick
    const scoreText = fixtureLegs.find((l) => l.scoreText)?.scoreText ?? null
    const movedTo = fixtureLegs.find((l) => l.rescheduledTo)?.rescheduledTo ?? null
    const buckets = new Map<string, SettledLeg[]>()
    for (const leg of fixtureLegs) {
      const { market, line, playLabel } = leg.pick
      const key = `${market}\0${line ?? ''}\0${playLabel}`
      const list = buckets.get(key) ?? []
      list.push(leg)
      buckets.set(key, list)
    }
    const rows = [...buckets.entries()].map(([key, list]) => {
      const sorted = [...list].sort(
        (a, b) =>
          OUTCOME_ORDER.indexOf(a.pick.outcome) -
          OUTCOME_ORDER.indexOf(b.pick.outcome),
      )
      return {
        key,
        playLabel: playLabelForRuleset(sorted[0].pick),
        picks: sorted.map((l) => ({
          key: `${l.pick.market}-${l.pick.outcome}`,
          label: `${outcomeTitle(l.pick.market, l.pick.outcome)}(${l.pick.odd})`,
          verdict: l.verdict,
        })),
      }
    })
    return {
      fixtureId: first.fixtureId,
      leagueId: first.leagueId,
      leagueName: first.leagueName,
      homeName: first.homeName,
      awayName: first.awayName,
      kickoff: first.kickoff,
      rescheduledLabel: movedTo
        ? `${formatDate(movedTo)} ${formatTime(movedTo)}`
        : null,
      scoreText,
      rows,
    }
  })
})

async function loadScores() {
  const current = plan.value
  if (!current) {
    scores.value = new Map()
    return
  }
  const ids = selectedFixtureIds(current.selections)
  if (!ids.length) {
    scores.value = new Map()
    return
  }
  loadingScores.value = true
  try {
    const data = await fetchFixtureScores(ids)
    const map = new Map<number, FixtureScoreSnap>()
    for (const row of data.fixtures) {
      map.set(row.fixture_id, row)
    }
    scores.value = map
  } catch (err) {
    message.error(err instanceof Error ? err.message : '加载赛果失败')
  } finally {
    loadingScores.value = false
  }
}

watch(
  () => props.planId,
  async (id) => {
    if (!id) {
      scores.value = new Map()
      return
    }
    await ensureLoaded()
    await loadScores()
  },
  { immediate: true },
)
</script>

<template>
  <n-empty v-if="!plan" description="方案不存在或已删除" />

  <n-spin v-else :show="loadingScores">
    <n-flex vertical :size="6">
      <n-descriptions
        class="plan-detail-summary"
        label-placement="left"
        :column="2"
        size="small"
        :label-style="{ width: '72px' }"
      >
        <n-descriptions-item label="过关">
          {{ foldModeLabel(plan.fold) }} · {{ plan.multiplier }} 倍
        </n-descriptions-item>
        <n-descriptions-item label="场次">
          <n-text type="success" strong>命中 {{ hitFixtureCount }}</n-text>
          <template v-if="voidFixtureCount">
            · <n-text type="warning" strong>走水 {{ voidFixtureCount }}</n-text>
          </template>
          / {{ selectedFixtureIds(plan.selections).length }} 场
        </n-descriptions-item>
        <n-descriptions-item label="状态">
          <n-tag
            size="small"
            :type="settlementStatusTagType"
            :disabled="settlement?.status === 'lost'"
            :bordered="false"
          >
            {{ settlement ? planStatusLabel(settlement.status) : '—' }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="保存日期">
          {{ plan.savedAt ? formatLocalDateMinute(plan.savedAt) : '—' }}
        </n-descriptions-item>
        <n-descriptions-item label="预计奖金">
          {{ settlement?.estimatedPrize ?? '—' }} 元
        </n-descriptions-item>
        <n-descriptions-item label="实际奖金">
          <n-text :type="actualPrizeTextType" strong>
            {{ actualPrizeText }}
          </n-text>
        </n-descriptions-item>
      </n-descriptions>

      <section
        v-for="group in legGroups"
        :key="group.fixtureId"
        class="leg-card"
      >
        <n-flex
          class="leg-card-header"
          :wrap="false"
          align="center"
          :size="8"
        >
          <n-ellipsis style="flex: 0 1 auto; min-width: 0;">
            <n-text :style="{ color: leagueTagColor(group.leagueId) }">
              {{ group.leagueName }}
            </n-text>
          </n-ellipsis>
          <n-text
            depth="3"
            style="flex-shrink: 0; font-size: 12px;"
            :delete="!!group.rescheduledLabel"
          >
            {{ group.kickoff }}
          </n-text>
          <n-tag
            v-if="group.rescheduledLabel"
            size="small"
            type="warning"
            :bordered="false"
          >
            已改期 → {{ group.rescheduledLabel }}
          </n-tag>
          <span v-if="group.scoreText" class="leg-score">
            比分
            <span class="leg-score-value">{{ group.scoreText }}</span>
          </span>
        </n-flex>

        <n-flex vertical :size="4">
          <FixtureMatchup
            :home-name="group.homeName"
            :away-name="group.awayName"
          />
          <n-flex
            v-for="row in group.rows"
            :key="row.key"
            :wrap="false"
            align="center"
            :size="6"
          >
            <n-tag size="small" :bordered="false">{{ row.playLabel }}</n-tag>
            <n-flex :size="6" align="center" style="flex-wrap: wrap;">
              <n-tag
                v-for="pick in row.picks"
                :key="pick.key"
                size="small"
                :bordered="false"
                :type="verdictType(pick.verdict)"
                :disabled="verdictDisabled(pick.verdict)"
              >
                {{ pick.label }} · {{ verdictLabel(pick.verdict) }}
              </n-tag>
            </n-flex>
          </n-flex>
        </n-flex>
      </section>
    </n-flex>
  </n-spin>
</template>

<style scoped>
.plan-detail-summary :deep(.n-descriptions-table-content__label) {
  color: var(--fa-text-secondary);
}

.plan-detail-summary :deep(.n-descriptions-table-content__content) {
  font-variant-numeric: tabular-nums;
}

.leg-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 8px;
  background: var(--fa-bg-soft);
}

.leg-card-header {
  min-width: 0;
  font-size: 12px;
  line-height: 1.3;
}

/* 比分与赛果页同一套高亮色，避免混在联赛/时间里看不见。 */
.leg-score {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--fa-text-secondary);
}

.leg-score-value {
  margin-left: 2px;
  color: var(--fa-highlight-text);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.leg-card :deep(.n-tag) {
  --n-height: 20px;
}
</style>
