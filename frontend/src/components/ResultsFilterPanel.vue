<script setup lang="ts">
import { ref } from 'vue'

import {
  RESULTS_HIT_OPTIONS,
  type ResultsFilterConfirm,
  type ResultsHitKey,
} from '@/utils/resultsPageState'

const props = withDefaults(
  defineProps<{
    initialHitKeys: ResultsHitKey[]
    initialHideWithoutPrediction?: boolean
    compactActions?: boolean
  }>(),
  { initialHideWithoutPrediction: false, compactActions: true },
)

const emit = defineEmits<{
  confirm: [payload: ResultsFilterConfirm]
}>()

const draftHits = ref<ResultsHitKey[]>([...props.initialHitKeys])
const hideWithoutPrediction = ref(props.initialHideWithoutPrediction)

const actionSize = props.compactActions ? 'tiny' : 'small'

function selectAll() {
  draftHits.value = RESULTS_HIT_OPTIONS.map((o) => o.key)
}

function confirm() {
  if (!draftHits.value.length) return
  emit('confirm', {
    hitKeys: [...draftHits.value],
    hideWithoutPrediction: hideWithoutPrediction.value,
  })
}
</script>

<template>
  <div class="results-filter-panel">
    <div class="section">
      <div class="section-title">赛前预测</div>
      <n-checkbox v-model:checked="hideWithoutPrediction">
        隐藏无赛前预测
      </n-checkbox>
    </div>
    <div class="section">
      <div class="section-title">预测结果</div>
      <n-checkbox-group v-model:value="draftHits">
        <n-space vertical :size="6">
          <n-checkbox
            v-for="opt in RESULTS_HIT_OPTIONS"
            :key="opt.key"
            :value="opt.key"
            :label="opt.label"
          />
        </n-space>
      </n-checkbox-group>
    </div>
    <n-space justify="end" :size="8" class="actions">
      <n-button :size="actionSize" @click.stop="selectAll">全选</n-button>
      <n-button :size="actionSize" type="primary" @click.stop="confirm">确认</n-button>
    </n-space>
  </div>
</template>

<style scoped>
.results-filter-panel {
  width: min(240px, 86vw);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-title {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--fa-text-muted);
  margin-bottom: 6px;
}

.actions {
  margin-top: 2px;
}
</style>
