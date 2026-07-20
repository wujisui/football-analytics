<script setup lang="ts">
import { FilterOutline } from '@vicons/ionicons5'
import { computed, ref, watch } from 'vue'

import type { ResultsHitKey } from '@/utils/resultsPageState'

const HIT_OPTIONS: { key: ResultsHitKey; label: string }[] = [
  { key: 'score', label: '比分' },
  { key: 'result', label: '胜平负' },
  { key: 'ou', label: '大小球' },
  { key: 'btts', label: '双方进球' },
]

const props = withDefaults(
  defineProps<{
    selectedHitKeys: ResultsHitKey[]
    filterActive?: boolean
  }>(),
  { filterActive: false },
)

const emit = defineEmits<{
  confirm: [hitKeys: ResultsHitKey[]]
}>()

const show = ref(false)
const draftHits = ref<ResultsHitKey[]>([])

const allHitKeys = computed(() => HIT_OPTIONS.map((o) => o.key))

watch(show, (open) => {
  if (!open) return
  draftHits.value = props.selectedHitKeys.length
    ? [...props.selectedHitKeys]
    : [...allHitKeys.value]
})

function selectAll() {
  draftHits.value = [...allHitKeys.value]
}

function confirm() {
  if (!draftHits.value.length) return
  emit('confirm', [...draftHits.value])
  show.value = false
}
</script>

<template>
  <n-popover
    v-model:show="show"
    trigger="click"
    placement="bottom-end"
    :show-arrow="false"
  >
    <template #trigger>
      <n-button
        size="tiny"
        quaternary
        :type="filterActive ? 'primary' : 'default'"
        aria-label="筛选赛果"
      >
        <template #icon>
          <n-icon :component="FilterOutline" :size="14" />
        </template>
        筛选
      </n-button>
    </template>
    <div class="results-filter-panel">
      <p class="hint">
        预测维度可多选；<strong>默认全部勾选</strong>。取消勾选即从列表中隐藏。
      </p>
      <div class="section">
        <div class="section-title">预测结果</div>
        <n-checkbox-group v-model:value="draftHits">
          <n-space vertical :size="6">
            <n-checkbox
              v-for="opt in HIT_OPTIONS"
              :key="opt.key"
              :value="opt.key"
              :label="opt.label"
            />
          </n-space>
        </n-checkbox-group>
      </div>
      <n-space justify="end" :size="8" class="actions">
        <n-button size="tiny" @click="selectAll">全选</n-button>
        <n-button size="tiny" type="primary" @click="confirm">确认</n-button>
      </n-space>
    </div>
  </n-popover>
</template>

<style scoped>
.results-filter-panel {
  width: min(240px, 86vw);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--fa-text-muted);
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
