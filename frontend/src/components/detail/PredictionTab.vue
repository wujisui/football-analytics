<script setup lang="ts">
import { computed, ref } from 'vue'

import OpinionInput from '@/components/detail/OpinionInput.vue'
import PredictionResult from '@/components/detail/PredictionResult.vue'
import { adjustFixturePrediction } from '@/api/fixtures'
import type { FixtureResponse, OddsPackage, PredictionSnapshot } from '@/api/types'
import { snapshotFromAnalysis } from '@/utils/opinionAdjust'
import { formatDateTime, formatOdd } from '@/utils/format'
import { teamNameZh } from '@/utils/teamNames'

const props = defineProps<{
  fixture: FixtureResponse
}>()

const selectedFactors = ref<string[]>([])
const submittedFactors = ref<string[]>([])
const submitting = ref(false)
const adjustError = ref('')
const adjusted = ref<PredictionSnapshot | null>(null)

const original = computed(() => snapshotFromAnalysis(props.fixture.analysis))
const oddsCurrent = computed(() => props.fixture.analysis.package?.odds ?? null)
const oddsOpening = computed(() => props.fixture.analysis.package?.odds_opening ?? null)

function ahLinesOf(odds: OddsPackage | null) {
  const market = odds?.asian_handicap
  if (!market) return []
  if (market.lines?.length) {
    return market.lines.filter((l) => l.line != null && l.line !== '')
  }
  if (market.line != null && market.line !== '') {
    return [{ line: market.line, home: market.home, away: market.away }]
  }
  return []
}

function hasMarkets(odds: OddsPackage | null) {
  if (!odds?.available) return false
  return !!(
    odds.match_winner ||
    odds.goals_ou ||
    ahLinesOf(odds).length
  )
}

const showCurrent = computed(() => hasMarkets(oddsCurrent.value))
const showOpening = computed(() => hasMarkets(oddsOpening.value))
const showAnyBoard = computed(() => showCurrent.value || showOpening.value)

const homeName = computed(() =>
  teamNameZh(props.fixture.home_team_name, props.fixture.home_team_id),
)
const awayName = computed(() =>
  teamNameZh(props.fixture.away_team_name, props.fixture.away_team_id),
)

async function submitOpinion() {
  if (!selectedFactors.value.length) return
  submitting.value = true
  adjustError.value = ''
  try {
    adjusted.value = await adjustFixturePrediction(
      props.fixture.fixture_id,
      selectedFactors.value,
    )
    submittedFactors.value = [...selectedFactors.value]
  } catch (e) {
    adjustError.value = e instanceof Error ? e.message : '融合预测失败'
    adjusted.value = null
    submittedFactors.value = []
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="prediction-tab">
    <template v-if="showAnyBoard">
      <n-card
        v-if="showCurrent"
        size="small"
        title="即时盘"
        style="background: var(--fa-bg-elevated);"
      >
        <template v-if="oddsCurrent?.captured_at" #header-extra>
          <n-text depth="3" style="font-size: 12px;">
            {{ formatDateTime(oddsCurrent.captured_at) }}
          </n-text>
        </template>
        <div class="markets">
          <div class="market-row market-head">
            <span class="market-label" />
            <span class="market-col">{{ homeName }}</span>
            <span class="market-col mid">盘口</span>
            <span class="market-col">{{ awayName }}</span>
          </div>
          <div v-if="oddsCurrent?.match_winner" class="market-row">
            <span class="market-label">胜平负</span>
            <span class="market-col">{{ formatOdd(oddsCurrent.match_winner.home) }}</span>
            <span class="market-col mid">{{ formatOdd(oddsCurrent.match_winner.draw) }}</span>
            <span class="market-col">{{ formatOdd(oddsCurrent.match_winner.away) }}</span>
          </div>
          <div
            v-for="(row, idx) in ahLinesOf(oddsCurrent)"
            :key="`cur-ah-${row.line}-${idx}`"
            class="market-row"
          >
            <span class="market-label">{{ idx === 0 ? '让球' : '' }}</span>
            <span class="market-col">{{ formatOdd(row.home) }}</span>
            <span class="market-col mid line">{{ row.line || '—' }}</span>
            <span class="market-col">{{ formatOdd(row.away) }}</span>
          </div>
          <div v-if="oddsCurrent?.goals_ou" class="market-row">
            <span class="market-label">大小</span>
            <span class="market-col">{{ formatOdd(oddsCurrent.goals_ou.home) }}</span>
            <span class="market-col mid line">{{ oddsCurrent.goals_ou.line || '—' }}</span>
            <span class="market-col">{{ formatOdd(oddsCurrent.goals_ou.away) }}</span>
          </div>
        </div>
      </n-card>

      <n-card
        v-if="showOpening"
        size="small"
        title="初盘"
        style="background: var(--fa-bg-elevated);"
      >
        <template v-if="oddsOpening?.captured_at" #header-extra>
          <n-text depth="3" style="font-size: 12px;">
            {{ formatDateTime(oddsOpening.captured_at) }}
          </n-text>
        </template>
        <div class="markets">
          <div class="market-row market-head">
            <span class="market-label" />
            <span class="market-col">{{ homeName }}</span>
            <span class="market-col mid">盘口</span>
            <span class="market-col">{{ awayName }}</span>
          </div>
          <div v-if="oddsOpening?.match_winner" class="market-row">
            <span class="market-label">胜平负</span>
            <span class="market-col">{{ formatOdd(oddsOpening.match_winner.home) }}</span>
            <span class="market-col mid">{{ formatOdd(oddsOpening.match_winner.draw) }}</span>
            <span class="market-col">{{ formatOdd(oddsOpening.match_winner.away) }}</span>
          </div>
          <div
            v-for="(row, idx) in ahLinesOf(oddsOpening)"
            :key="`open-ah-${row.line}-${idx}`"
            class="market-row"
          >
            <span class="market-label">{{ idx === 0 ? '让球' : '' }}</span>
            <span class="market-col">{{ formatOdd(row.home) }}</span>
            <span class="market-col mid line">{{ row.line || '—' }}</span>
            <span class="market-col">{{ formatOdd(row.away) }}</span>
          </div>
          <div v-if="oddsOpening?.goals_ou" class="market-row">
            <span class="market-label">大小</span>
            <span class="market-col">{{ formatOdd(oddsOpening.goals_ou.home) }}</span>
            <span class="market-col mid line">{{ oddsOpening.goals_ou.line || '—' }}</span>
            <span class="market-col">{{ formatOdd(oddsOpening.goals_ou.away) }}</span>
          </div>
        </div>
      </n-card>
    </template>

    <OpinionInput
      v-model="selectedFactors"
      :submitting="submitting"
      @submit="submitOpinion"
    />
    <n-alert v-if="adjustError" type="error" :title="adjustError" />
    <PredictionResult
      :original="original"
      :adjusted="adjusted"
      :data-source="fixture.analysis.data_source"
      :analyzed-at="formatDateTime(fixture.analysis.analyzed_at)"
      :comparing="submitting"
      :has-opinion="submittedFactors.length > 0"
    />
  </div>
</template>

<style scoped>
.prediction-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.markets {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.market-row {
  display: grid;
  grid-template-columns: 56px 1fr 72px 1fr;
  gap: 8px;
  align-items: center;
}

.market-head {
  color: var(--fa-text-faint);
  font-size: 12px;
}

.market-label {
  color: var(--fa-text-secondary);
}

.market-col {
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.market-col.mid.line {
  font-weight: 600;
  color: var(--fa-text-strong);
}
</style>
