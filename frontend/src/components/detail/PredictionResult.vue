<script setup lang="ts">
import { computed } from 'vue'

import ProbabilityChart from '@/components/ProbabilityChart.vue'
import type { PredictionSnapshot } from '@/api/types'
import { predictionDiffKeys } from '@/utils/opinionAdjust'
import { confidenceType, toPercent } from '@/utils/format'

const props = defineProps<{
  original: PredictionSnapshot
  adjusted: PredictionSnapshot | null
  confidence: string
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
</script>

<template>
  <section class="prediction-result">
    <div class="head">
      <h2 class="section-title">预测对比</h2>
      <div class="meta">
        <n-tag size="small" :type="confidenceType(confidence)" :bordered="false">
          数据完整度 {{ confidence }}
        </n-tag>
        <span class="muted">来源 {{ dataSource }} · {{ analyzedAt }}</span>
      </div>
    </div>

    <n-spin :show="!!comparing">
      <div class="compare-grid">
        <n-card size="small" title="算法原始预测" class="panel">
          <div class="rec">
            推荐
            <n-tag
              :type="original.recommendation === '待分析' ? 'default' : 'primary'"
              size="small"
            >
              {{ original.recommendation }}
            </n-tag>
          </div>
          <ul class="rows">
            <li>主胜 {{ toPercent(original.home_win_prob) }}</li>
            <li>平局 {{ toPercent(original.draw_prob) }}</li>
            <li>客胜 {{ toPercent(original.away_win_prob) }}</li>
            <li class="soft">{{ original.goal_lean }}</li>
            <li class="soft">{{ original.both_score_lean }}</li>
            <li class="soft">{{ original.handicap_lean }}</li>
            <li class="soft">参考比分 {{ original.score_hint }}</li>
          </ul>
          <ProbabilityChart
            :probabilities="{
              home_win_prob: original.home_win_prob,
              draw_prob: original.draw_prob,
              away_win_prob: original.away_win_prob,
            }"
            compact
          />
        </n-card>

        <n-card size="small" class="panel" :class="{ highlight: hasOpinion && adjusted }">
          <template #header>
            <span>{{ hasOpinion && adjusted ? '融合主观意见' : '融合主观意见（待提交）' }}</span>
          </template>

          <template v-if="adjusted && hasOpinion">
            <div class="rec" :class="rowClass('recommendation')">
              推荐
              <n-tag type="success" size="small">{{ adjusted.recommendation }}</n-tag>
            </div>
            <ul class="rows">
              <li :class="rowClass('home')">主胜 {{ toPercent(adjusted.home_win_prob) }}</li>
              <li :class="rowClass('draw')">平局 {{ toPercent(adjusted.draw_prob) }}</li>
              <li :class="rowClass('away')">客胜 {{ toPercent(adjusted.away_win_prob) }}</li>
              <li class="soft" :class="rowClass('goal_lean')">{{ adjusted.goal_lean }}</li>
              <li class="soft" :class="rowClass('both_score')">{{ adjusted.both_score_lean }}</li>
              <li class="soft" :class="rowClass('handicap')">{{ adjusted.handicap_lean }}</li>
              <li class="soft" :class="rowClass('score')">参考比分 {{ adjusted.score_hint }}</li>
            </ul>
            <ProbabilityChart
              :probabilities="{
                home_win_prob: adjusted.home_win_prob,
                draw_prob: adjusted.draw_prob,
                away_win_prob: adjusted.away_win_prob,
              }"
              compact
            />
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
  gap: 8px;
  margin-bottom: 10px;
  font-size: 14px;
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

@media (max-width: 900px) {
  .compare-grid {
    grid-template-columns: 1fr;
  }
}
</style>
