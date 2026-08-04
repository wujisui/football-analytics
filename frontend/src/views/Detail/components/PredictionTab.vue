<script setup lang="ts">
import { computed } from 'vue'

import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import PredictionResult from '@/views/Detail/components/PredictionResult.vue'
import type { FixtureResponse } from '@/api/types'
import { formatDateTime } from '@/utils/format'
import { hasOddsMarkets, isDistinctCurrentOdds } from '@/utils/oddsDisplay'

const props = defineProps<{
  fixture: FixtureResponse
}>()

const oddsCurrent = computed(() => props.fixture.analysis.package?.odds ?? null)
const oddsOpening = computed(() => props.fixture.analysis.package?.odds_opening ?? null)

const hasCurrent = computed(() => hasOddsMarkets(oddsCurrent.value))
const hasOpening = computed(() => hasOddsMarkets(oddsOpening.value))

/** First freeze copies current → opening at the same instant; hide duplicate 即时盘. */
const showCurrent = computed(
  () =>
    hasCurrent.value
    && (!hasOpening.value || isDistinctCurrentOdds(oddsCurrent.value, oddsOpening.value)),
)
const showOpening = computed(() => hasOpening.value)
const showAnyBoard = computed(() => showCurrent.value || showOpening.value)

const isFinished = computed(
  () => (props.fixture.status ?? '').toLowerCase() === 'finished',
)
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
        <PreMatchOddsTable :odds="oddsCurrent" />
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
        <PreMatchOddsTable :odds="oddsOpening" />
      </n-card>
    </template>

    <PredictionResult
      :fixture="fixture"
      :is-finished="isFinished"
      :data-source="fixture.analysis.data_source"
      :analyzed-at="formatDateTime(fixture.analysis.analyzed_at)"
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
