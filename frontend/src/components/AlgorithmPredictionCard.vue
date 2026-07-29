<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import type { FixtureResponse } from '@/api/types'
import { hasRealProbabilities, toPercent } from '@/utils/format'
import { fixtureDetailRoute, type DetailFrom } from '@/utils/detailNav'
import { snapshotFromAnalysis, type PredictionSnapshot } from '@/utils/opinionAdjust'
import {
  HANDICAP_MISSING_LABEL,
  isHandicapPending,
} from '@/utils/handicapDisplay'

const props = withDefaults(
  defineProps<{
    fixture?: FixtureResponse
    snapshot?: PredictionSnapshot
    fixtureId?: number
    /** Elevated card for the predictions list. */
    standalone?: boolean
    /** Show home vs away title link above recommendation row. */
    showMatchupTitle?: boolean
    from?: DetailFrom
    date?: string | null
  }>(),
  {
    standalone: false,
    showMatchupTitle: true,
    from: 'home',
    date: null,
  },
)

const router = useRouter()

const resolvedFixtureId = computed(
  () => props.fixture?.fixture_id ?? props.fixtureId ?? null,
)

const prediction = computed((): PredictionSnapshot => {
  if (props.snapshot) return props.snapshot
  if (props.fixture) return snapshotFromAnalysis(props.fixture.analysis)
  return {
    home_win_prob: 0,
    draw_prob: 0,
    away_win_prob: 0,
    recommendation: '待分析',
    goal_lean: '',
    both_score_lean: '',
    score_hint: '',
    handicap_lean: '',
    probabilitiesAvailable: false,
  }
})

const predictionReady = computed(() => {
  if (props.snapshot) return props.snapshot.probabilitiesAvailable
  if (!props.fixture) return false
  return hasRealProbabilities(
    props.fixture.analysis.probabilities,
    prediction.value.recommendation,
  )
})

const recommendationPending = computed(
  () => !predictionReady.value || prediction.value.recommendation === '待分析',
)
const handicapPending = computed(() =>
  isHandicapPending(prediction.value.handicap_lean),
)

const homeName = computed(() => props.fixture?.home_team_name || '—')
const awayName = computed(() => props.fixture?.away_team_name || '—')
const matchupTitle = computed(() => `${homeName.value} vs ${awayName.value}`)

const probs = computed(() => {
  if (!predictionReady.value) return []
  return [
    { key: 'home', label: '主胜', value: prediction.value.home_win_prob },
    { key: 'draw', label: '平局', value: prediction.value.draw_prob },
    { key: 'away', label: '客胜', value: prediction.value.away_win_prob },
  ]
})

function goStats() {
  if (resolvedFixtureId.value == null) return
  void router.push(
    fixtureDetailRoute(resolvedFixtureId.value, {
      from: props.from,
      tab: 'record',
      date: props.date,
    }),
  )
}

function goBriefing() {
  if (resolvedFixtureId.value == null) return
  void router.push(
    fixtureDetailRoute(resolvedFixtureId.value, {
      from: props.from,
      tab: 'briefing',
      date: props.date,
    }),
  )
}
</script>

<template>
  <component
    :is="standalone ? 'article' : 'section'"
    class="predict-card"
    :class="{ standalone, zone: !standalone }"
  >
    <div class="rec-row">
      <n-button
        v-if="showMatchupTitle"
        text
        type="primary"
        size="small"
        class="zone-matchup"
        @click.stop="goStats"
      >
        {{ matchupTitle }}
      </n-button>
      <n-button
        text
        size="small"
        class="rec-label"
        @click.stop="goBriefing"
      >
        推荐
      </n-button>
      <n-tag
        :type="recommendationPending ? 'default' : 'primary'"
        size="small"
        class="rec-chip"
        @click.stop="goBriefing"
      >
        {{ prediction.recommendation }}
      </n-tag>
      <n-tag
        :type="handicapPending ? 'default' : 'warning'"
        size="small"
        class="rec-tag rec-chip"
        @click.stop="goBriefing"
      >
        {{ prediction.handicap_lean || HANDICAP_MISSING_LABEL }}
      </n-tag>
    </div>
    <div v-if="predictionReady" class="prob-row">
      <div v-for="p in probs" :key="p.key" class="prob-item">
        <span class="prob-head">
          <span>{{ p.label }}</span>
          <strong>{{ toPercent(p.value) }}</strong>
        </span>
        <n-progress
          type="line"
          :percentage="Math.round(p.value * 100)"
          :show-indicator="false"
          :height="standalone ? 6 : 8"
          processing
        />
      </div>
    </div>
    <p v-else class="predict-empty">暂无有效胜平负概率（缺近况或盘口）</p>
    <div v-if="predictionReady" class="lean-row">
      <n-tag size="small" :bordered="false">{{ prediction.goal_lean }}</n-tag>
      <n-tag size="small" :bordered="false">{{ prediction.both_score_lean }}</n-tag>
      <n-tag size="small" :bordered="false" type="info">
        {{ prediction.score_hint }}
      </n-tag>
    </div>
    <div v-else-if="!handicapPending" class="lean-row">
      <n-tag size="small" :bordered="false" type="warning">
        {{ prediction.handicap_lean }}
      </n-tag>
    </div>
  </component>
</template>

<style scoped>
.predict-card.zone {
  background: var(--fa-bg-soft);
  border-radius: 6px;
  padding: 12px;
  min-width: 0;
  height: 100%;
  box-sizing: border-box;
}

.predict-card.standalone {
  background: var(--fa-bg-elevated);
  border: 1px solid var(--fa-border);
  border-radius: 8px;
  padding: 14px;
  min-width: 0;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.predict-card.standalone:hover {
  border-color: var(--fa-hover-border);
  box-shadow: 0 2px 10px var(--fa-hover-shadow);
}

.rec-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.zone-matchup {
  max-width: 100%;
  white-space: normal;
  height: auto;
  line-height: 1.4;
  padding: 0 2px;
  flex-shrink: 0;
}

.rec-label {
  font-size: 13px;
  color: var(--fa-text-secondary);
  flex-shrink: 0;
  padding: 0 2px;
  height: auto;
}

.rec-chip {
  cursor: pointer;
}

.rec-tag {
  max-width: 100%;
  white-space: normal;
  height: auto;
  line-height: 1.4;
  padding: 2px 8px;
}

.prob-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 6px;
}

.prob-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.prob-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px;
  font-size: 11px;
  line-height: 1.2;
  color: var(--fa-text-faint);
}

.prob-head strong {
  color: var(--fa-text-strong);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.lean-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.predict-empty {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--fa-text-faint);
}

.predict-card.standalone .rec-row,
.predict-card.standalone .prob-row {
  margin-bottom: 10px;
}

.predict-card.standalone .prob-item {
  gap: 4px;
}

.predict-card.standalone .prob-head {
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  font-size: 12px;
}

.predict-card.standalone .prob-head strong {
  font-size: 16px;
  font-weight: 700;
}
</style>
