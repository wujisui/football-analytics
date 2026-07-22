<script setup lang="ts">
import {
  RESULTS_ALL_HIT_KEYS,
  RESULTS_HIT_OPTIONS,
  type ResultsHitKey,
} from '@/utils/resultsPageState'

const props = withDefaults(
  defineProps<{
    compactActions?: boolean
  }>(),
  { compactActions: true },
)

const draftHits = defineModel<ResultsHitKey[]>('draftHits', { required: true })
const hideWithoutPrediction = defineModel<boolean>('hideWithoutPrediction', {
  required: true,
})

const emit = defineEmits<{
  confirm: []
}>()

const actionSize = props.compactActions ? 'tiny' : 'small'

function selectAllHits() {
  draftHits.value = [...RESULTS_ALL_HIT_KEYS]
}

function confirm() {
  if (!draftHits.value.length) return
  emit('confirm')
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
      <n-button :size="actionSize" @click="selectAllHits">全选维度</n-button>
      <n-button :size="actionSize" type="primary" @click="confirm">确认</n-button>
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
