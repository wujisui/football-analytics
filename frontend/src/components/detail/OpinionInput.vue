<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  modelValue: string
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  submit: []
}>()

const local = ref(props.modelValue)

watch(
  () => props.modelValue,
  (v) => {
    if (v !== local.value) local.value = v
  },
)

function onInput(v: string) {
  local.value = v
  emit('update:modelValue', v)
}

function onSubmit() {
  emit('submit')
}
</script>

<template>
  <section class="opinion-input">
    <n-card size="small" title="我的主观意见">
      <p class="hint">
        结合伤病、体能、轮换等主观判断；提交后与算法原始预测做本地融合对比（后端暂无 /predict）。
      </p>
      <n-input
        :value="local"
        type="textarea"
        :rows="8"
        placeholder="例如：主队近期赛程密集，体能存疑；客队主力前锋复出，进攻端威胁大增。"
        maxlength="800"
        show-count
        @update:value="onInput"
      />
      <div class="actions">
        <n-button
          type="primary"
          :loading="submitting"
          :disabled="!local.trim()"
          @click="onSubmit"
        >
          提交意见并重新预测
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

.actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
