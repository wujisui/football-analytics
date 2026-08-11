<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'

import { fetchFixtureScores } from '@/api/fixtures'
import { useBetPlans } from '@/composables/useBetPlans'
import FixtureMatchup from '@/components/FixtureMatchup.vue'
import {
  foldModeLabel,
  outcomeTitle,
  selectedFixtureIds,
  type CalcOutcome,
} from '@/utils/betCalculator'
import { leagueTagColor } from '@/utils/format'
import {
  planStatusLabel,
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
const { getPlan, reload } = useBetPlans()

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
  )
})

function verdictLabel(v: LegVerdict): string {
  if (v === 'hit') return '中'
  if (v === 'miss') return '未中'
  if (v === 'void') return '走水'
  return '待定'
}

function verdictType(v: LegVerdict): 'success' | 'error' | 'warning' | 'default' {
  if (v === 'hit') return 'success'
  if (v === 'miss') return 'error'
  if (v === 'void') return 'warning'
  return 'default'
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
  scoreText: string | null
  rows: {
    key: string
    playLabel: string
    picks: { key: string; label: string; verdict: LegVerdict }[]
  }[]
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
        playLabel: sorted[0].pick.playLabel,
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
    await reload()
    await loadScores()
  },
  { immediate: true },
)
</script>

<template>
  <n-empty v-if="!plan" description="方案不存在或已删除" />

  <n-spin v-else :show="loadingScores">
    <n-space vertical :size="0">
      <n-card size="small" :bordered="false">
        <n-descriptions label-placement="left" :column="1" size="small">
          <n-descriptions-item label="过关">
            {{ foldModeLabel(plan.fold) }} · {{ plan.multiplier }} 倍
          </n-descriptions-item>
          <n-descriptions-item label="场次">
            {{ selectedFixtureIds(plan.selections).length }} 场
          </n-descriptions-item>
          <n-descriptions-item label="状态">
            <n-tag
              size="small"
              :type="
                settlement?.status === 'won'
                  ? 'success'
                  : settlement?.status === 'lost'
                    ? 'error'
                    : settlement?.status === 'void'
                      ? 'warning'
                      : 'default'
              "
              :bordered="false"
            >
              {{ settlement ? planStatusLabel(settlement.status) : '—' }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="投入">
            {{ settlement?.stakeYuan ?? '—' }} 元
          </n-descriptions-item>
          <n-descriptions-item label="预计奖金">
            {{ settlement?.estimatedPrize ?? '—' }} 元
          </n-descriptions-item>
          <n-descriptions-item label="实际奖金">
            <n-text
              :type="settlement?.status === 'won' ? 'error' : undefined"
              strong
            >
              {{
                settlement?.status === 'pending'
                  ? '待结算'
                  : `${settlement?.actualPrize ?? 0} 元`
              }}
            </n-text>
          </n-descriptions-item>
        </n-descriptions>
        <n-text depth="3" class="plan-detail-hint">
          走水场次赔率按1计，取消/延期场次作废。
        </n-text>
      </n-card>

      <n-card size="small"  :bordered="false">
        <n-flex vertical :size="0">
          <n-card
            v-for="group in legGroups"
            :key="group.fixtureId"
            size="small"
            :bordered="false"
            class="leg-card"
          >
            <template #header>
              <n-flex :wrap="false" align="center" :size="8" style="min-width: 0;">
                <n-ellipsis style="flex: 0 1 auto; min-width: 0;">
                  <n-text :style="{ color: leagueTagColor(group.leagueId) }">
                    {{ group.leagueName }}
                  </n-text>
                </n-ellipsis>
                <n-text depth="3" style="flex-shrink: 0; font-size: 12px;">
                  {{ group.kickoff }}
                </n-text>
                <span v-if="group.scoreText" class="leg-score">
                  比分
                  <span class="leg-score-value">{{ group.scoreText }}</span>
                </span>
              </n-flex>
            </template>

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
                  >
                    {{ pick.label }} · {{ verdictLabel(pick.verdict) }}
                  </n-tag>
                </n-flex>
              </n-flex>
            </n-flex>
          </n-card>
        </n-flex>
      </n-card>
    </n-space>
  </n-spin>
</template>

<style scoped>
.plan-detail-hint {
  display: block;
  margin-top: 8px;
  font-size: 12px;
}

.leg-card {
  background: var(--fa-bg-soft);
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

/* Match the compact metrics used by 投注详情 (BetSelectionList). */
.leg-card :deep(.n-card-header) {
  padding: 5px 8px 0;
  line-height: 1.3;
}

.leg-card :deep(.n-card__content) {
  padding: 4px 8px 6px;
}

.leg-card :deep(.n-card-header__main) {
  min-width: 0;
  font-size: 12px;
}

.leg-card :deep(.n-tag) {
  --n-height: 20px;
}
</style>
