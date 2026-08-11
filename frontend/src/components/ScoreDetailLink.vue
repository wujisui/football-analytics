<script setup lang="ts">
import { computed } from 'vue'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  label: string
}>()

defineEmits<{
  click: []
}>()

const hasScore = computed(() => /\d+\s*[:：-]\s*\d+/.test(props.label))
</script>

<template>
  <n-button
    v-bind="$attrs"
    text
    class="score-detail-link"
    :class="{ 'has-score': hasScore }"
    aria-label="查看详细分析"
    @click="$emit('click')"
  >
    {{ label }}
  </n-button>
</template>

<style scoped>
.score-detail-link {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--fa-text-strong);
}

.score-detail-link.has-score {
  color: var(--fa-highlight-text);
}

.score-detail-link.has-score:hover {
  filter: brightness(1.15);
}
</style>
