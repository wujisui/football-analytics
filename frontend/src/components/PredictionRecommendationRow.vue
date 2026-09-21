<script setup lang="ts">
import { computed } from 'vue'

import type { AutoFavoriteMarket } from '@/api/favorites'
import { autoFavoritePick } from '@/composables/useFavoriteFixtures'
import { isPredictionPending, adaptHandicapLean } from '@/utils/handicapDisplay'
const props = withDefaults(
  defineProps<{
    recommendation?: string
    handicapLean?: string
    goalLean?: string
    bothScore?: string
    scoreHint?: string
    referenceLean?: string | null
    referenceEv?: number | null
    referenceAdjustedEv?: number | null
    referenceProbability?: number | null
    referenceAlignment?: string | null
    referenceReason?: string | null
    clickable?: boolean
    /** Resolves the auto-favorite market/lean for this fixture. */
    fixtureId?: number | null
  }>(),
  {
    recommendation: '待分析',
    handicapLean: '',
    goalLean: '',
    bothScore: '',
    scoreHint: '',
    referenceLean: null,
    referenceEv: null,
    referenceAdjustedEv: null,
    referenceProbability: null,
    referenceAlignment: null,
    referenceReason: null,
    clickable: false,
    fixtureId: null,
  },
)

const emit = defineEmits<{
  open: []
}>()

/**
 * 日推优先从独赢/让球中单选，不足时按大小球、双进降级补位。
 * 被日推选中的场次整行改用日推那套自洽三件套，禁止两套混排。
 */
const pick = computed(() => autoFavoritePick(props.fixtureId))

function isPick(market: AutoFavoriteMarket): boolean {
  return pick.value?.market === market
}

/** 有 [荐] 时整行只展示日推自洽三件套，禁止与分析器 handicap/score 混排。 */
const recommendationText = computed(() => {
  if (isPick('1x2')) return pick.value?.marketLean || pick.value?.lean
  if (pick.value) return pick.value.lean
  return props.recommendation
})
const handicapText = computed(() => {
  if (isPick('ah')) return pick.value?.marketLean
  if (pick.value) return pick.value.handicapLean
  return props.handicapLean
})
const goalText = computed(() =>
  isPick('ou') ? pick.value?.marketLean || props.goalLean : props.goalLean,
)
const bothScoreText = computed(() =>
  isPick('btts') ? pick.value?.marketLean || props.bothScore : props.bothScore,
)
const scoreText = computed(() => {
  if (pick.value) return pick.value.scoreHint
  return props.scoreHint
})

const recommendationLabel = computed(() =>
  isPredictionPending(recommendationText.value)
    ? '待分析'
    : recommendationText.value,
)
const handicapLabel = computed(() => adaptHandicapLean(handicapText.value))
const showHandicap = computed(() => !isPredictionPending(handicapText.value))
const showGoal = computed(() => !isPredictionPending(goalText.value))
const showBothScore = computed(() => !isPredictionPending(bothScoreText.value))
const showScore = computed(() => !isPredictionPending(scoreText.value))
const referenceText = computed(() => {
  if (!props.referenceLean) return ''
  const probability = props.referenceProbability == null
    ? ''
    : ` · 校准概率 ${(props.referenceProbability * 100).toFixed(1)}%`
  const ev = props.referenceEv == null
    ? ' · EV 数据不足'
    : ` · EV ${props.referenceEv >= 0 ? '+' : ''}${(props.referenceEv * 100).toFixed(1)}%`
  const adjusted = props.referenceAdjustedEv == null
    ? ''
    : ` · 调整后 ${props.referenceAdjustedEv >= 0 ? '+' : ''}${(props.referenceAdjustedEv * 100).toFixed(1)}%`
  const alignmentLabel = {
    aligned_strong: '盘口强一致',
    aligned_weak: '盘口一致',
    unknown: '盘口方向不明确',
    reverse_weak: '逆向推荐（弱）',
    reverse_strong: '逆向推荐（强）',
  }[props.referenceAlignment || '']
  const alignment = alignmentLabel
    ? ` · ${alignmentLabel}`
    : ''
  return `参考 ${props.referenceLean}${probability}${ev}${adjusted}${alignment}`
})

/**
 * 普通场次统一 info；每日推荐场次只突出实际主推，其他预测退为 default。
 * 赛前没有命中态，主推借用赛果命中 tag 的 error 红色建立一致视觉。
 */
function tagType(market?: AutoFavoriteMarket): 'error' | 'default' | 'info' {
  if (!pick.value) return 'info'
  return market && isPick(market) ? 'error' : 'default'
}

function open() {
  if (props.clickable) emit('open')
}
</script>

<template>
  <div
    class="recommendation-row"
    :class="{ clickable }"
    :role="clickable ? 'button' : undefined"
    :tabindex="clickable ? 0 : undefined"
    @click.stop="open"
    @keydown.enter.prevent="open"
    @keydown.space.prevent="open"
  >
    <n-tag
      size="small"
      class="rec-tag"
      :class="{ 'rec-pick': isPick('1x2') }"
      :bordered="false"
      :type="tagType('1x2')"
    >
      <span v-if="isPick('1x2')" class="rec-pick-mark">[荐]</span>
      {{ recommendationLabel }}
    </n-tag>
    <n-tag
      v-if="showHandicap"
      size="small"
      class="handicap-tag rec-tag"
      :class="{ 'rec-pick': isPick('ah') }"
      :bordered="false"
      :type="tagType('ah')"
    >
      <span v-if="isPick('ah')" class="rec-pick-mark">[荐]</span>
      <n-ellipsis style="max-width: 100%">{{ handicapLabel }}</n-ellipsis>
    </n-tag>
    <n-tag
      v-if="showGoal"
      size="small"
      class="rec-tag"
      :class="{ 'rec-pick': isPick('ou') }"
      :type="tagType('ou')"
      :bordered="false"
    >
      <span v-if="isPick('ou')" class="rec-pick-mark">[荐]</span>
      {{ goalText }}
    </n-tag>
    <n-tag
      v-if="showBothScore"
      size="small"
      class="rec-tag"
      :class="{ 'rec-pick': isPick('btts') }"
      :type="tagType('btts')"
      :bordered="false"
    >
      <span v-if="isPick('btts')" class="rec-pick-mark">[荐]</span>
      {{ bothScoreText }}
    </n-tag>
    <n-tag
      v-if="showScore"
      size="small"
      class="score-tag rec-tag"
      :bordered="false"
      :type="tagType()"
    >
      <n-ellipsis style="max-width: 100%">{{ scoreText }}</n-ellipsis>
    </n-tag>
    <span
      v-if="referenceText"
      class="reference-summary"
      :title="referenceReason || referenceText"
    >{{ referenceText }}</span>
  </div>
</template>

<style scoped>
.recommendation-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.recommendation-row :deep(.n-tag) {
  flex-shrink: 0;
}

.handicap-tag,
.score-tag {
  flex-shrink: 1;
  max-width: min(100%, 220px);
  height: auto;
  padding: 2px 8px;
  line-height: 1.4;
}

.handicap-tag :deep(.n-tag__content),
.score-tag :deep(.n-tag__content) {
  display: block;
  min-width: 0;
  max-width: 100%;
}

.rec-pick-mark {
  margin-right: 3px;
  font-size: 11px;
  opacity: 0.95;
}

.reference-summary {
  flex-basis: 100%;
  color: var(--n-text-color-3);
  font-size: 12px;
}

.clickable {
  cursor: pointer;
}
</style>
