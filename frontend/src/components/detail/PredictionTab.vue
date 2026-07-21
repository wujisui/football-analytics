<script setup lang="ts">
import { computed, ref } from 'vue'

import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import OpinionInput from '@/components/detail/OpinionInput.vue'
import PredictionResult from '@/components/detail/PredictionResult.vue'
import { adjustFixturePrediction } from '@/api/fixtures'
import type { FixtureResponse } from '@/api/types'
import { snapshotFromAnalysis, snapshotFromApi, type PredictionSnapshot } from '@/utils/opinionAdjust'
import { formatDateTime } from '@/utils/format'
import { hasOddsMarkets } from '@/utils/oddsDisplay'

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

const showCurrent = computed(() => hasOddsMarkets(oddsCurrent.value))
const showOpening = computed(() => hasOddsMarkets(oddsOpening.value))
const showAnyBoard = computed(() => showCurrent.value || showOpening.value)

const homeName = computed(() => props.fixture.home_team_name || '—')
const awayName = computed(() => props.fixture.away_team_name || '—')
const isFinished = computed(
  () => (props.fixture.status ?? '').toLowerCase() === 'finished',
)

async function submitOpinion() {
  if (!selectedFactors.value.length) return
  submitting.value = true
  adjustError.value = ''
  try {
    adjusted.value = snapshotFromApi(
      await adjustFixturePrediction(
        props.fixture.fixture_id,
        selectedFactors.value,
      ),
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
        <PreMatchOddsTable
          :odds="oddsCurrent"
          :home-name="homeName"
          :away-name="awayName"
        />
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
        <PreMatchOddsTable
          :odds="oddsOpening"
          :home-name="homeName"
          :away-name="awayName"
        />
      </n-card>
    </template>

    <OpinionInput
      v-model="selectedFactors"
      :submitting="submitting"
      @submit="submitOpinion"
    />
    <n-alert v-if="adjustError" type="error" :title="adjustError" />
    <PredictionResult
      :fixture="fixture"
      :is-finished="isFinished"
      :original="original"
      :adjusted="adjusted"
      :data-source="fixture.analysis.data_source"
      :analyzed-at="formatDateTime(fixture.analysis.analyzed_at)"
      :comparing="submitting"
      :has-opinion="submittedFactors.length > 0"
      :handicap-market-note="fixture.analysis.handicap_market_note || ''"
    />
  </div>
</template>

<style scoped>
.prediction-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
