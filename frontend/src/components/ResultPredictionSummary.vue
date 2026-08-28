<script setup lang="ts">
import { computed } from 'vue'

import ResultHitTags from '@/components/ResultHitTags.vue'
import WdlProbabilityBars from '@/components/WdlProbabilityBars.vue'
import type { HitTagFixture } from '@/utils/resultsDisplay'
import type { ResultsHitKey } from '@/utils/resultsPageState'

/** Prediction fields shown on the results list card. */
export type ResultPredictionFields = HitTagFixture & {
  recommendation?: string | null
  score_hint?: string | null
  goal_lean?: string | null
  both_score_lean?: string | null
  probabilities_available?: boolean
  home_win_prob?: number | null
  draw_prob?: number | null
  away_win_prob?: number | null
}

const props = withDefaults(defineProps<{
  fixture: ResultPredictionFields
  oddsClickable?: boolean
  showProbabilities?: boolean
  hitFilterable?: boolean
  activeHitKey?: ResultsHitKey | null
}>(), {
  oddsClickable: false,
  showProbabilities: false,
  hitFilterable: false,
  activeHitKey: null,
})

const emit = defineEmits<{
  openOdds: []
  filterHit: [key: ResultsHitKey]
}>()

const probabilities = computed(() => {
  if (!props.showProbabilities || !props.fixture.probabilities_available) return []
  return [
    { key: 'home', label: '主胜', value: Number(props.fixture.home_win_prob ?? 0) },
    { key: 'draw', label: '平局', value: Number(props.fixture.draw_prob ?? 0) },
    { key: 'away', label: '客胜', value: Number(props.fixture.away_win_prob ?? 0) },
  ]
})
</script>

<template>
  <div
    v-if="fixture.has_prediction"
    class="result-prediction-summary"
    :class="{
      'odds-clickable': oddsClickable,
      'with-probabilities': probabilities.length,
    }"
    :role="oddsClickable ? 'button' : undefined"
    :tabindex="oddsClickable ? 0 : undefined"
    @click="oddsClickable && emit('openOdds')"
    @keydown.enter.prevent="oddsClickable && emit('openOdds')"
    @keydown.space.prevent="oddsClickable && emit('openOdds')"
  >
    <n-text depth="3" class="pred-line">
      {{ fixture.recommendation || '—' }}
      · {{ fixture.handicap_lean || '—' }}
      · {{ fixture.score_hint || '—' }}
      · {{ fixture.goal_lean || '—' }}
      · {{ fixture.both_score_lean || '—' }}
    </n-text>
    <WdlProbabilityBars v-if="probabilities.length" :items="probabilities" />
    <ResultHitTags
      :fixture="fixture"
      :filterable="hitFilterable"
      :active-hit-key="activeHitKey"
      @filter-hit="emit('filterHit', $event)"
    />
  </div>
  <n-text v-else depth="3" class="no-pred">无赛前预测</n-text>
</template>

<style scoped>
.result-prediction-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
}

.result-prediction-summary.with-probabilities {
  gap: 6px;
}

.result-prediction-summary.odds-clickable {
  padding: 4px;
  margin: -4px;
  border-radius: var(--fa-radius-card);
  cursor: pointer;
}

.result-prediction-summary.odds-clickable:hover,
.result-prediction-summary.odds-clickable:focus-visible {
  outline: none;
  background: var(--fa-bg-elevated);
}

.pred-line {
  display: block;
  font-size: 11px;
  line-height: 1.45;
  overflow-wrap: anywhere;
  word-break: break-word;
  user-select: none;
}

.no-pred {
  font-size: 11px;
}
</style>
