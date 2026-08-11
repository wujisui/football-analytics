<script setup lang="ts">
import { computed } from 'vue'

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
  }>(),
  {
    recommendation: '待分析',
    handicapLean: '',
    goalLean: '',
    bothScore: '',
    scoreHint: '',
    clickable: false,
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
      :bordered="false"
      :type="recommendationTagColor ? undefined : 'default'"
      :color="recommendationTagColor"
    >
      {{ recommendationLabel }}
    </n-tag>
    <n-tag
      v-if="showHandicap"
      size="small"
      class="handicap-tag"
      :bordered="false"
      :type="handicapTagColor ? undefined : 'default'"
      :color="handicapTagColor"
    >
      <n-ellipsis style="max-width: 100%">{{ handicapLabel }}</n-ellipsis>
    </n-tag>
    <n-tag v-if="showGoal" size="small" type="warning" :bordered="false">
      {{ goalLean }}
    </n-tag>
    <n-tag v-if="showBothScore" size="small" :bordered="false">
      {{ bothScore }}
    </n-tag>
    <n-tag v-if="showScore" size="small" class="score-tag" :bordered="false" type="info">
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

.clickable {
  cursor: pointer;
}
</style>
