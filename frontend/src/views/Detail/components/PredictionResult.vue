<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import type { FixtureResponse } from '@/api/types'
import { snapshotFromAnalysis } from '@/utils/opinionAdjust'
import { toPercent } from '@/utils/format'
import { adaptHandicapLean, HANDICAP_MISSING_LABEL } from '@/utils/handicapDisplay'
import { useHandicapRuleset } from '@/composables/useHandicapRuleset'
import { leanWdlTone, wdlTagColor } from '@/theme/wdlColors'

/** echarts is heavy; load the pie only when a prediction renders. */
const ProbabilityChart = defineAsyncComponent(
  () => import('@/views/Detail/components/ProbabilityChart.vue'),
)

const props = defineProps<{
  fixture: FixtureResponse
  isFinished?: boolean
  dataSource: string
  analyzedAt: string
  handicapMarketNote?: string
}>()

const original = computed(() => snapshotFromAnalysis(props.fixture.analysis))
const explanation = computed(
  () =>
    props.fixture.analysis.market_analysis ?? {
      available: false,
      title: '盘口解释',
      paragraphs: ['暂无后端盘口解释，请刷新详情后重试。'],
      bullets: [],
      warnings: [],
      stage_count: 0,
    },
)
const { ruleset } = useHandicapRuleset()
const handicapLabel = computed(
  () =>
    adaptHandicapLean(original.value.handicap_lean, ruleset.value) ||
    HANDICAP_MISSING_LABEL,
)

const recommendationTagColor = computed(() =>
  wdlTagColor(leanWdlTone(original.value.recommendation)),
)
const handicapTagColor = computed(() =>
  wdlTagColor(leanWdlTone(handicapLabel.value)),
)
const matchupText = computed(
  () =>
    `${props.fixture.home_team_name || '—'} vs ${props.fixture.away_team_name || '—'}`,
)

</script>

<template>
  <section class="prediction-result">
    <div class="head">
      <h2 class="section-title">预测对比</h2>
      <div class="meta">
        <span class="muted">来源 {{ dataSource }} · {{ analyzedAt }}</span>
      </div>
    </div>

    <div class="compare-grid">
      <n-card
        v-if="isFinished"
        size="small"
        title="赛前结果预测"
        class="panel"
      >
        <template #header-extra>
          <n-text depth="3" class="matchup">{{ matchupText }}</n-text>
        </template>
        <AlgorithmPredictionCard :fixture="fixture" />
      </n-card>
      <n-card v-else size="small" title="算法原始预测" class="panel">
        <template #header-extra>
          <n-text depth="3" class="matchup">{{ matchupText }}</n-text>
        </template>
        <div class="algo-body" :class="{ 'no-chart': !original.probabilitiesAvailable }">
          <div class="algo-copy">
            <div class="rec">
              推荐
              <n-tag
                size="small"
                :bordered="false"
                :type="recommendationTagColor ? undefined : 'default'"
                :color="recommendationTagColor"
              >
                {{ original.recommendation }}
              </n-tag>
              <n-tag
                size="small"
                class="rec-tag"
                :bordered="false"
                :type="handicapTagColor ? undefined : 'default'"
                :color="handicapTagColor"
              >
                {{ handicapLabel }}
              </n-tag>
            </div>
            <p v-if="handicapMarketNote" class="handicap-note">{{ handicapMarketNote }}</p>
            <ul v-if="original.probabilitiesAvailable" class="rows">
              <li class="tone-win">主胜 {{ toPercent(original.home_win_prob) }}</li>
              <li class="tone-draw">平局 {{ toPercent(original.draw_prob) }}</li>
              <li class="tone-loss">客胜 {{ toPercent(original.away_win_prob) }}</li>
              <li class="soft">{{ original.goal_lean }}</li>
              <li class="soft">{{ original.both_score_lean }}</li>
              <li class="soft">{{ original.score_hint }}</li>
            </ul>
            <p v-else class="empty-probs">暂无有效胜平负概率（缺近况或盘口），不展示占位百分比</p>
          </div>
          <ProbabilityChart
            v-if="original.probabilitiesAvailable"
            class="algo-chart"
            :probabilities="{
              available: true,
              home_win_prob: original.home_win_prob,
              draw_prob: original.draw_prob,
              away_win_prob: original.away_win_prob,
            }"
            compact
          />
        </div>
      </n-card>

      <n-card size="small" class="panel" :title="explanation.title">
        <template #header-extra>
          <n-text depth="3" class="matchup">{{ matchupText }}</n-text>
        </template>
        <div class="explain">
          <p
            v-for="(p, idx) in explanation.paragraphs"
            :key="`p-${idx}`"
            class="explain-p"
          >
            {{ p }}
          </p>
          <ul v-if="explanation.bullets.length" class="explain-bullets">
            <li v-for="(b, idx) in explanation.bullets" :key="`b-${idx}`">
              {{ b }}
            </li>
          </ul>
          <n-alert
            v-if="explanation.warnings.length"
            type="warning"
            :bordered="false"
            class="explain-warning"
          >
            <div
              v-for="(warning, idx) in explanation.warnings"
              :key="`warning-${idx}`"
            >
              {{ warning }}
            </div>
          </n-alert>
        </div>
      </n-card>
    </div>
  </section>
</template>

<style scoped>
.prediction-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--fa-text-strong);
}

.meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.muted {
  font-size: 12px;
  color: var(--fa-text-faint);
}

.compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.panel {
  background: var(--fa-bg-elevated);
  min-height: 0;
}

.matchup {
  display: block;
  max-width: min(46vw, 220px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.rec {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 14px;
}

.rec-tag {
  max-width: 100%;
  white-space: normal;
  height: auto;
  line-height: 1.4;
  padding: 2px 8px;
}

.handicap-note {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--fa-text-faint);
}

.algo-body {
  display: flex;
  align-items: stretch;
  gap: 8px;
  min-width: 0;
}

.algo-copy {
  flex: 0 1 auto;
  max-width: 42%;
  min-width: 0;
}

.algo-body.no-chart .algo-copy {
  max-width: none;
  flex: 1 1 auto;
}

.algo-chart {
  flex: 1 1 auto;
  min-width: 0;
  width: auto;
  align-self: stretch;
  display: flex;
}

.algo-body :deep(.chart.compact) {
  height: 100%;
  min-height: 200px;
}

.rows {
  margin: 0;
  padding-left: 18px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--fa-text);
  white-space: nowrap;
}

.rows .tone-win,
.rows .tone-draw,
.rows .tone-loss {
  font-weight: 700;
}

.rows .tone-win {
  color: var(--fa-wdl-win);
}

.rows .tone-draw {
  color: var(--fa-wdl-draw);
}

.rows .tone-loss {
  color: var(--fa-wdl-loss);
}

.rows .tone-win::marker {
  color: var(--fa-wdl-win);
}

.rows .tone-draw::marker {
  color: var(--fa-wdl-draw);
}

.rows .tone-loss::marker {
  color: var(--fa-wdl-loss);
}

.rows .soft {
  color: var(--fa-text-secondary);
  font-size: 13px;
  font-weight: 400;
  white-space: normal;
  max-width: 11em;
}

.empty-probs {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--fa-text-faint);
  line-height: 1.5;
}

.explain {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.explain-p {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: var(--fa-text);
}

.explain-bullets {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--fa-text-secondary);
}

.explain-warning {
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 900px) {
  .compare-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .algo-body {
    flex-direction: column;
    align-items: stretch;
  }

  .algo-copy {
    flex: none;
    max-width: none;
    width: 100%;
  }

  .algo-chart {
    flex: none;
    width: 100%;
  }

  .rows {
    white-space: normal;
  }

  .rows .soft {
    max-width: none;
  }

  .algo-body :deep(.chart.compact) {
    height: 200px;
    min-height: 200px;
  }
}
</style>
