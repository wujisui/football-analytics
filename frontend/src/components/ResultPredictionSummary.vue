<script setup lang="ts">
import ResultHitTags from '@/components/ResultHitTags.vue'
import type { HitTagFixture } from '@/utils/resultsDisplay'

/** Prediction fields shown on the results list card. */
export type ResultPredictionFields = HitTagFixture & {
  recommendation?: string | null
  handicap_lean?: string | null
  score_hint?: string | null
  goal_lean?: string | null
  both_score_lean?: string | null
}

withDefaults(defineProps<{
  fixture: ResultPredictionFields
  oddsClickable?: boolean
}>(), {
  oddsClickable: false,
})

const emit = defineEmits<{
  openOdds: []
}>()
</script>

<template>
  <div
    v-if="fixture.has_prediction"
    class="result-prediction-summary"
    :class="{ 'odds-clickable': oddsClickable }"
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
    <ResultHitTags :fixture="fixture" />
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

.result-prediction-summary.odds-clickable {
  padding: 4px;
  margin: -4px;
  border-radius: 6px;
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
}

.no-pred {
  font-size: 11px;
}
</style>
