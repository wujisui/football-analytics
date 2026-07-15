<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import type { FixtureResponse } from '@/api/types'
import { hasRealProbabilities, toPercent } from '@/utils/format'
import { snapshotFromAnalysis } from '@/utils/opinionAdjust'

const props = withDefaults(
  defineProps<{
    fixture: FixtureResponse
    /** Elevated card for the predictions list; embedded zone inside FixtureCard. */
    standalone?: boolean
    /** Navigate to fixture detail on click (standalone implies true). */
    linkToDetail?: boolean
    /** Breadcrumb back target on detail. */
    from?: 'home' | 'predictions'
  }>(),
  { standalone: false, linkToDetail: false, from: 'home' },
)

const router = useRouter()

const canNavigate = computed(() => props.standalone || props.linkToDetail)

const prediction = computed(() => snapshotFromAnalysis(props.fixture.analysis))
const predictionReady = computed(() =>
  hasRealProbabilities(
    props.fixture.analysis.probabilities,
    prediction.value.recommendation,
  ),
)
const recommendationPending = computed(
  () => !predictionReady.value || prediction.value.recommendation === '待分析',
)
const handicapPending = computed(() => {
  const text = prediction.value.handicap_lean || ''
  return !text || text.includes('缺少盘口') || text.includes('待分析')
})

const homeName = computed(() => props.fixture.home_team_name || '—')
const awayName = computed(() => props.fixture.away_team_name || '—')
const matchupTitle = computed(() => `${homeName.value} vs ${awayName.value}`)

const probs = computed(() => {
  if (!predictionReady.value) return []
  return [
    { key: 'home', label: '主胜', value: prediction.value.home_win_prob },
    { key: 'draw', label: '平局', value: prediction.value.draw_prob },
    { key: 'away', label: '客胜', value: prediction.value.away_win_prob },
  ]
})

function goDetail() {
  if (!canNavigate.value) return
  void router.push({
    name: 'fixture-detail',
    params: { fixtureId: props.fixture.fixture_id },
    query: { from: props.from },
  })
}
</script>

<template>
  <component
    :is="standalone ? 'article' : 'section'"
    class="predict-card"
    :class="{
      standalone,
      zone: !standalone,
      clickable: canNavigate,
    }"
    :role="canNavigate ? 'link' : undefined"
    :tabindex="canNavigate ? 0 : undefined"
    @click="goDetail"
    @keydown.enter="goDetail"
  >
    <h3 class="zone-title">
      算法预测
      <span class="zone-matchup">{{ matchupTitle }}</span>
    </h3>
    <div class="rec-row">
      <span class="rec-label">推荐</span>
      <n-tag :type="recommendationPending ? 'default' : 'primary'" size="small">
        {{ prediction.recommendation }}
      </n-tag>
      <n-tag
        :type="handicapPending ? 'default' : 'warning'"
        size="small"
        class="rec-tag"
      >
        {{ prediction.handicap_lean || '缺少盘口数据分析' }}
      </n-tag>
    </div>
    <div v-if="predictionReady" class="prob-row">
      <div v-for="p in probs" :key="p.key" class="prob-item">
        <span class="prob-label">{{ p.label }}</span>
        <span class="prob-value">{{ toPercent(p.value) }}</span>
        <n-progress
          type="line"
          :percentage="Math.round(p.value * 100)"
          :show-indicator="false"
          :height="6"
          processing
        />
      </div>
    </div>
    <p v-else class="predict-empty">暂无有效胜平负概率（缺近况或盘口）</p>
    <div v-if="predictionReady" class="lean-row">
      <n-tag size="small" :bordered="false">{{ prediction.goal_lean }}</n-tag>
      <n-tag size="small" :bordered="false">{{ prediction.both_score_lean }}</n-tag>
      <n-tag size="small" :bordered="false" type="info">
        参考比分 {{ prediction.score_hint }}
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
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.predict-card.standalone:hover,
.predict-card.clickable:hover {
  border-color: var(--fa-hover-border);
  box-shadow: 0 2px 10px var(--fa-hover-shadow);
}

.predict-card.clickable {
  cursor: pointer;
}

.predict-card.clickable:focus-visible {
  outline: 2px solid var(--fa-highlight-border);
  outline-offset: 2px;
}

.zone-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--fa-text-secondary);
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 10px;
}

.zone-matchup {
  font-weight: 500;
  color: var(--fa-text);
  font-size: 12px;
}

.rec-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.rec-label {
  font-size: 13px;
  color: var(--fa-text-secondary);
  flex-shrink: 0;
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
  margin-bottom: 10px;
}

.prob-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.prob-label {
  font-size: 12px;
  color: var(--fa-text-faint);
}

.prob-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--fa-text-strong);
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
</style>
