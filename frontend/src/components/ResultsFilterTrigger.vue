<script setup lang="ts">
import { FilterOutline } from '@vicons/ionicons5'
import { ref, watch } from 'vue'

import ResultsFilterPanel from '@/components/ResultsFilterPanel.vue'
import {
  RESULTS_ALL_HIT_KEYS,
  type ResultsFilterConfirm,
  type ResultsHitKey,
} from '@/utils/resultsPageState'

withDefaults(
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
const panelKey = ref(0)

watch(show, (open) => {
  if (open) panelKey.value += 1
})

function confirm(payload: ResultsFilterConfirm) {
  if (!payload.hitKeys.length) return
  emit('confirm', payload)
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
      v-if="show"
      :key="panelKey"
      :initial-hit-keys="
        selectedHitKeys.length ? [...selectedHitKeys] : [...RESULTS_ALL_HIT_KEYS]
      "
      :initial-hide-without-prediction="hideWithoutPrediction"
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
