<script setup lang="ts">
import { computed } from 'vue'

import type { AutoFavoriteMarket } from '@/api/favorites'
import RecommendationStrength from '@/components/RecommendationStrength.vue'
import { autoFavoritePick, favoriteQualityRating } from '@/composables/useFavoriteFixtures'
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
    /**
     * 行尾自带星级/参考槽位。宿主卡片已有让球行那个预留位时置 false，
     * 避免同一场比赛出现两份推荐强度。
     */
    inlineStrength?: boolean
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
    inlineStrength: true,
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
/** 同一槽位：日推场次给星级，其余场次给每场参考。 */
const qualityRating = computed(() => favoriteQualityRating(props.fixtureId))

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
    <RecommendationStrength
      v-if="inlineStrength"
      :value="qualityRating"
      :reference-lean="referenceLean"
      :reference-ev="referenceEv"
      :reference-adjusted-ev="referenceAdjustedEv"
      :reference-probability="referenceProbability"
      :reference-alignment="referenceAlignment"
      :reference-reason="referenceReason"
      @click.stop
    />
  </div>
</template>

<style scoped>
/*
 * 整行既是「赛前简报」的悬停触发区，又是点进详情的按钮，所以必须贴着标签收窄：
 * 撑满宿主宽度时，标签右侧的空白也会弹浮层并吃掉点击。
 */
.recommendation-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-self: start;
  align-self: start;
  gap: 6px;
  width: fit-content;
  min-width: 0;
  max-width: 100%;
}

.recommendation-row :deep(.n-tag) {
  flex-shrink: 0;
}

/* n-tag 自带 cursor: default，会在可点整行里露出箭头光标 */
.clickable :deep(.n-tag) {
  cursor: inherit;
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

.clickable {
  cursor: pointer;
}
</style>
