<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchOpinionFactors } from '@/api/fixtures'
import type { OpinionFactor } from '@/api/types'

const props = defineProps<{
  modelValue: string[]
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
  submit: []
}>()

const factors = ref<OpinionFactor[]>([])
const loadError = ref('')
const loadingFactors = ref(false)

const selected = computed({
  get: () => props.modelValue,
  set: (v: string[]) => emit('update:modelValue', v),
})

const grouped = computed(() => {
  const map = new Map<string, OpinionFactor[]>()
  for (const f of factors.value) {
    const list = map.get(f.group) || []
    list.push(f)
    map.set(f.group, list)
  }
  return [...map.entries()]
})

onMounted(async () => {
  loadingFactors.value = true
  loadError.value = ''
  try {
    factors.value = await fetchOpinionFactors()
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '加载因素失败'
  } finally {
    loadingFactors.value = false
  }
})

function setChecked(id: string, checked: boolean) {
  const set = new Set(selected.value)
  if (checked) set.add(id)
  else set.delete(id)
  selected.value = [...set]
}

function onSubmit() {
  if (!selected.value.length) return
  emit('submit')
}
</script>

<template>
  <section class="opinion-input">
    <n-card size="small" title="主观因素（勾选）">
      <p class="hint">
        这不是 AI 自由文本分析。勾选你认可的赛前因素后，由后端按固定权重与算法预测融合对比。
      </p>
      <n-spin :show="loadingFactors">
        <n-alert v-if="loadError" type="error" :title="loadError" style="margin-bottom: 12px" />
        <div v-for="[group, items] in grouped" :key="group" class="group">
          <div class="group-title">{{ group }}</div>
          <div class="tags">
            <n-tag
              v-for="f in items"
              :key="f.id"
              checkable
              :checked="selected.includes(f.id)"
              :bordered="false"
              @update:checked="(v) => setChecked(f.id, !!v)"
            >
              {{ f.label }}
            </n-tag>
          </div>
        </div>
      </n-spin>
      <div class="actions">
        <n-button
          type="primary"
          :loading="submitting"
          :disabled="!selected.length"
          @click="onSubmit"
        >
          提交因素并重新预测
        </n-button>
      </div>
    </n-card>
  </section>
</template>

<style scoped>
.opinion-input {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--fa-text-muted);
  line-height: 1.5;
}

.group {
  margin-bottom: 12px;
}

.group:last-of-type {
  margin-bottom: 0;
}

.group-title {
  font-size: 12px;
  color: var(--fa-text-faint);
  margin-bottom: 8px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
