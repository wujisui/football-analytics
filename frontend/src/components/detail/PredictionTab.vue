<script setup lang="ts">
import { computed, ref } from 'vue'

import OpinionInput from '@/components/detail/OpinionInput.vue'
import PredictionResult from '@/components/detail/PredictionResult.vue'
import { adjustFixturePrediction } from '@/api/fixtures'
import type { FixtureResponse, PredictionSnapshot } from '@/api/types'
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
const odds = computed(() => props.fixture.analysis.package?.odds ?? null)
const mw = computed(() => odds.value?.match_winner ?? null)
const ou = computed(() => odds.value?.goals_ou ?? null)
const ahLines = computed(() => {
  const market = odds.value?.asian_handicap
  if (!market) return []
  if (market.lines?.length) {
    return market.lines.filter((l) => l.line != null && l.line !== '')
  }
  if (market.line != null && market.line !== '') {
    return [{ line: market.line, home: market.home, away: market.away }]
  }
  return []
})
const hasMarkets = computed(
  () => !!(mw.value || ou.value || ahLines.value.length),
)

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
    <n-card v-if="hasMarkets" size="small" title="赛前盘口" style="background: var(--fa-bg-elevated);">
      <div class="markets">
        <div class="market-row market-head">
          <span class="market-label" />
          <span class="market-col">{{ homeName }}</span>
          <span class="market-col mid">盘口</span>
          <span class="market-col">{{ awayName }}</span>
        </div>
        <div v-if="mw" class="market-row">
          <span class="market-label">胜平负</span>
          <span class="market-col">{{ formatOdd(mw.home) }}</span>
          <span class="market-col mid">{{ formatOdd(mw.draw) }}</span>
          <span class="market-col">{{ formatOdd(mw.away) }}</span>
        </div>
        <div
          v-for="(row, idx) in ahLines"
          :key="`ah-${row.line}-${idx}`"
          class="market-row"
        >
          <span class="market-label">{{ idx === 0 ? '让球' : '' }}</span>
          <span class="market-col">{{ formatOdd(row.home) }}</span>
          <span class="market-col mid line">{{ row.line || '—' }}</span>
          <span class="market-col">{{ formatOdd(row.away) }}</span>
        </div>
        <div v-if="ou" class="market-row">
          <span class="market-label">大小</span>
          <span class="market-col">{{ formatOdd(ou.home) }}</span>
          <span class="market-col mid line">{{ ou.line || '—' }}</span>
          <span class="market-col">{{ formatOdd(ou.away) }}</span>
        </div>
      </div>
    </n-card>

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
