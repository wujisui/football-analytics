<script setup lang="ts">
import { computed } from 'vue'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import ProbabilityChart from '@/components/ProbabilityChart.vue'
import type { FixtureResponse } from '@/api/types'
import { predictionDiffKeys, type PredictionSnapshot } from '@/utils/opinionAdjust'
import { toPercent } from '@/utils/format'

const props = defineProps<{
  fixture?: FixtureResponse
  isFinished?: boolean
  original: PredictionSnapshot
  adjusted: PredictionSnapshot | null
  dataSource: string
  analyzedAt: string
  comparing?: boolean
  hasOpinion?: boolean
}>()

const diffKeys = computed(() => {
  if (!props.adjusted) return new Set<string>()
  return predictionDiffKeys(props.original, props.adjusted)
})

function rowClass(key: string): string {
  return diffKeys.value.has(key) ? 'diff' : ''
}

function isPendingRec(text: string): boolean {
  return !text || text === '待分析'
}

function isPendingHandicap(text: string): boolean {
  return !text || text.includes('缺少盘口') || text.includes('待分析')
}
</script>

<template>
  <section class="prediction-result">
    <div class="head">
      <h2 class="section-title">预测对比</h2>
      <div class="meta">
        <span class="muted">来源 {{ dataSource }} · {{ analyzedAt }}</span>
      </div>
    </div>

    <n-spin :show="!!comparing">
      <div class="compare-grid">
        <n-card
          v-if="isFinished && fixture"
          size="small"
          title="赛前结果预测"
          class="panel"
        >
          <AlgorithmPredictionCard :fixture="fixture" />
        </n-card>
        <n-card v-else size="small" title="算法原始预测" class="panel">
          <div class="rec">
            推荐
            <n-tag
              :type="isPendingRec(original.recommendation) ? 'default' : 'primary'"
              size="small"
            >
              {{ original.recommendation }}
            </n-tag>
            <n-tag
              :type="isPendingHandicap(original.handicap_lean) ? 'default' : 'warning'"
              size="small"
              class="rec-tag"
            >
              {{ original.handicap_lean || '缺少盘口数据分析' }}
            </n-tag>
          </div>
          <template v-if="original.probabilitiesAvailable">
            <ul class="rows">
              <li>主胜 {{ toPercent(original.home_win_prob) }}</li>
              <li>平局 {{ toPercent(original.draw_prob) }}</li>
              <li>客胜 {{ toPercent(original.away_win_prob) }}</li>
              <li class="soft">{{ original.goal_lean }}</li>
              <li class="soft">{{ original.both_score_lean }}</li>
              <li class="soft">参考比分 {{ original.score_hint }}</li>
            </ul>
            <ProbabilityChart
              :probabilities="{
                available: true,
                home_win_prob: original.home_win_prob,
                draw_prob: original.draw_prob,
                away_win_prob: original.away_win_prob,
              }"
              compact
            />
          </template>
          <p v-else class="empty-probs">暂无有效胜平负概率（缺近况或盘口），不展示占位百分比</p>
        </n-card>

        <n-card size="small" class="panel" :class="{ highlight: hasOpinion && adjusted }">
          <template #header>
            <span>{{ hasOpinion && adjusted ? '融合主观意见' : '融合主观意见（待提交）' }}</span>
          </template>

          <template v-if="adjusted && hasOpinion">
            <div
              class="rec"
              :class="{
                diff: diffKeys.has('recommendation') || diffKeys.has('handicap'),
              }"
            >
              推荐
              <n-tag
                type="success"
                size="small"
                :class="rowClass('recommendation')"
              >
                {{ adjusted.recommendation }}
              </n-tag>
              <n-tag
                type="warning"
                size="small"
                class="rec-tag"
                :class="rowClass('handicap')"
              >
                {{ adjusted.handicap_lean || '缺少盘口数据分析' }}
              </n-tag>
            </div>
            <template v-if="adjusted.probabilitiesAvailable">
              <ul class="rows">
                <li :class="rowClass('home')">主胜 {{ toPercent(adjusted.home_win_prob) }}</li>
                <li :class="rowClass('draw')">平局 {{ toPercent(adjusted.draw_prob) }}</li>
                <li :class="rowClass('away')">客胜 {{ toPercent(adjusted.away_win_prob) }}</li>
                <li class="soft" :class="rowClass('goal_lean')">{{ adjusted.goal_lean }}</li>
                <li class="soft" :class="rowClass('both_score')">{{ adjusted.both_score_lean }}</li>
                <li class="soft" :class="rowClass('score')">参考比分 {{ adjusted.score_hint }}</li>
              </ul>
              <ProbabilityChart
                :probabilities="{
                  available: true,
                  home_win_prob: adjusted.home_win_prob,
                  draw_prob: adjusted.draw_prob,
                  away_win_prob: adjusted.away_win_prob,
                }"
                compact
              />
            </template>
            <p v-else class="empty-probs">暂无有效胜平负概率</p>
            <p v-if="diffKeys.size === 0" class="note">意见未触发明显方向调整</p>
            <p v-else class="note changed">高亮项为相对算法结果发生变化的结论</p>
          </template>
          <n-empty
            v-else
            description="在上方勾选主观因素并提交后，此处显示融合结果"
            size="small"
            class="empty"
          />
        </n-card>
      </div>
    </n-spin>
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

.panel.highlight {
  border-color: #8fd3a8;
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

.rows {
  margin: 0 0 8px;
  padding-left: 18px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--fa-text);
}

.rows .soft {
  color: var(--fa-text-secondary);
  font-size: 13px;
}

.rows .diff,
.rec.diff {
  background: var(--fa-highlight-bg);
  border-radius: 4px;
  padding: 0 6px;
  margin-left: -6px;
  color: var(--fa-highlight-text);
  font-weight: 600;
}

.note {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--fa-text-faint);
}

.note.changed {
  color: var(--fa-highlight-text);
}

.empty {
  padding: 40px 0;
}

.empty-probs {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--fa-text-faint);
  line-height: 1.5;
}

@media (max-width: 900px) {
  .compare-grid {
    grid-template-columns: 1fr;
  }
}
</style>
