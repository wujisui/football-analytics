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
    /** 每场参考只用于给对应玩法的标签着色，不再单独展示。 */
    referenceMarket?: AutoFavoriteMarket | string | null
    referenceLean?: string | null
    referenceProbability?: number | null
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
    referenceMarket: null,
    referenceLean: null,
    referenceProbability: null,
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

/**
 * 每场参考是与分析器并行的另一条轨道，方向可以不同。整行文案恒取同一来源
 * （有 [荐] 用日推三件套，否则全用分析器），只在参考方向与本行已展示的方向
 * 一致时才着色：否则会把「双进否 + 比分 2-0」标成看好「双进是」。
 */
function isReference(market: AutoFavoriteMarket, shownLean: string): boolean {
  return (
    !pick.value
    && props.referenceMarket === market
    && props.referenceProbability != null
    && props.referenceLean !== '数据不足'
    && sameDirection(market, shownLean, props.referenceLean || '')
  )
}

/** 同玩法两段文案是否指向同一侧；让球与独赢按整串比，大小球和双进只看方向字。 */
function sameDirection(
  market: AutoFavoriteMarket,
  shown: string,
  reference: string,
): boolean {
  const a = shown.trim()
  const b = reference.trim()
  if (!a || !b) return false
  if (market === 'ou') return a.startsWith('大') === b.startsWith('大')
  if (market === 'btts') return a.includes('是') === b.includes('是')
  return a === b
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
/** 本行该玩法实际展示的文案，着色前用它与参考方向比对。 */
function shownLean(market: AutoFavoriteMarket): string {
  if (market === '1x2') return recommendationText.value || ''
  if (market === 'ah') return handicapText.value || ''
  if (market === 'ou') return goalText.value || ''
  return bothScoreText.value || ''
}

/**
 * 普通场次用 success 标出统一决策链选出的每场参考，其余保持 info；
 * 每日推荐场次只突出实际主推，其他预测退为 default。
 * 赛前没有命中态，主推借用赛果命中 tag 的 error 红色建立一致视觉。
 */
function tagType(
  market?: AutoFavoriteMarket,
): 'error' | 'success' | 'default' | 'info' {
  if (!pick.value) {
    return market && isReference(market, shownLean(market)) ? 'success' : 'info'
  }
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

/*
 * 手机上整行只占一行：超宽时由让球/比分标签的省略号吸收。靠换行让步会让
 * 同一列卡片高度在一行与两行之间跳。
 */
@media (max-width: 767px) {
  .recommendation-row {
    flex-wrap: nowrap;
  }
}
</style>
