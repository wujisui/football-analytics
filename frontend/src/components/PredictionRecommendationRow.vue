<script setup lang="ts">
import { computed } from 'vue'

import type { AutoFavoriteMarket } from '@/api/favorites'
import { leanWdlTone, wdlTagColor } from '@/theme/wdlColors'
import { isPredictionPending } from '@/utils/handicapDisplay'

const props = withDefaults(
  defineProps<{
    recommendation?: string
    handicapLean?: string
    goalLean?: string
    bothScore?: string
    scoreHint?: string
    clickable?: boolean
    /** When set (auto favorite), mark that market with the recommend color. */
    highlightMarket?: AutoFavoriteMarket | string | null
  }>(),
  {
    recommendation: '待分析',
    handicapLean: '',
    goalLean: '',
    bothScore: '',
    scoreHint: '',
    clickable: false,
    highlightMarket: null,
  },
)

const emit = defineEmits<{
  open: []
}>()

const recommendationLabel = computed(() =>
  isPredictionPending(props.recommendation) ? '待分析' : props.recommendation,
)
const recommendationTagColor = computed(() =>
  isPredictionPending(props.recommendation)
    ? undefined
    : wdlTagColor(leanWdlTone(props.recommendation)),
)
const handicapLabel = computed(() => (props.handicapLean || '').trim())
const showHandicap = computed(() => !isPredictionPending(props.handicapLean))
const handicapTagColor = computed(() =>
  wdlTagColor(leanWdlTone(props.handicapLean)),
)
const showGoal = computed(() => !isPredictionPending(props.goalLean))
const showBothScore = computed(() => !isPredictionPending(props.bothScore))
const showScore = computed(() => !isPredictionPending(props.scoreHint))

const pickMarket = computed(() => (props.highlightMarket || '').trim())

function isPick(market: AutoFavoriteMarket): boolean {
  return pickMarket.value === market
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
      :type="recommendationTagColor ? undefined : 'default'"
      :color="isPick('1x2') ? undefined : recommendationTagColor"
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
      :type="handicapTagColor ? undefined : 'default'"
      :color="isPick('ah') ? undefined : handicapTagColor"
    >
      <span v-if="isPick('ah')" class="rec-pick-mark">[荐]</span>
      <n-ellipsis style="max-width: 100%">{{ handicapLabel }}</n-ellipsis>
    </n-tag>
    <n-tag
      v-if="showGoal"
      size="small"
      class="rec-tag"
      :class="{ 'rec-pick': isPick('ou') }"
      :type="isPick('ou') ? undefined : 'warning'"
      :bordered="false"
    >
      <span v-if="isPick('ou')" class="rec-pick-mark">[荐]</span>
      {{ goalLean }}
    </n-tag>
    <n-tag
      v-if="showBothScore"
      size="small"
      class="rec-tag"
      :class="{ 'rec-pick': isPick('btts') }"
      :bordered="false"
    >
      <span v-if="isPick('btts')" class="rec-pick-mark">[荐]</span>
      {{ bothScore }}
    </n-tag>
    <n-tag
      v-if="showScore"
      size="small"
      class="score-tag rec-tag"
      :class="{ 'rec-pick': isPick('score') }"
      :bordered="false"
      :type="isPick('score') ? undefined : 'info'"
    >
      <span v-if="isPick('score')" class="rec-pick-mark">[荐]</span>
      <n-ellipsis style="max-width: 100%">{{ scoreHint }}</n-ellipsis>
    </n-tag>
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

.rec-tag.rec-pick {
  color: var(--fa-highlight-text) !important;
  background: var(--fa-highlight-bg) !important;
  box-shadow: inset 0 0 0 1px var(--fa-highlight-border);
  font-weight: 600;
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
