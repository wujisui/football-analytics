<script setup lang="ts">
import { FilterOutline } from '@vicons/ionicons5'
import { ref, watch } from 'vue'

import ResultsFilterPanel from '@/components/ResultsFilterPanel.vue'
import {
  RESULTS_ALL_HIT_KEYS,
  type ResultsFilterConfirm,
  type ResultsHitKey,
} from '@/utils/resultsPageState'

const props = withDefaults(
  defineProps<{
    selectedHitKeys: ResultsHitKey[]
    hideWithoutPrediction?: boolean
    filterActive?: boolean
  }>(),
  { hideWithoutPrediction: false, filterActive: false },
)

const emit = defineEmits<{
  confirm: [payload: ResultsFilterConfirm]
}>()

const show = ref(false)
const draftHits = ref<ResultsHitKey[]>([])
const draftHideWithoutPrediction = ref(false)

watch(show, (open) => {
  if (!open) return
  draftHits.value = props.selectedHitKeys.length
    ? [...props.selectedHitKeys]
    : [...RESULTS_ALL_HIT_KEYS]
  draftHideWithoutPrediction.value = props.hideWithoutPrediction
})

function confirm() {
  if (!draftHits.value.length) return
  emit('confirm', {
    hitKeys: [...draftHits.value],
    hideWithoutPrediction: draftHideWithoutPrediction.value,
  })
  show.value = false
}
</script>

<template>
  <n-popover
    v-model:show="show"
    trigger="hover"
    :delay="80"
    :duration="180"
    placement="left-start"
    :show-arrow="false"
    display-directive="show"
    to="body"
  >
    <template #trigger>
      <n-button
        size="small"
        quaternary
        class="results-filter-btn"
        :type="filterActive ? 'primary' : 'default'"
        aria-label="筛选赛果"
      >
        <template #icon>
          <n-icon :component="FilterOutline" :size="14" />
        </template>
        筛选
      </n-button>
    </template>
    <ResultsFilterPanel
      v-model:draft-hits="draftHits"
      v-model:hide-without-prediction="draftHideWithoutPrediction"
      compact-actions
      @confirm="confirm"
    />
  </n-popover>
</template>

<style scoped>
.results-filter-btn {
  flex-shrink: 0;
  padding-inline: 10px;
}
</style>
