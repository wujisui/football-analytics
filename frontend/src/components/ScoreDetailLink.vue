<script setup lang="ts">
import { computed } from 'vue'

import { FIXTURE_DETAIL_TOOLTIP } from '@/utils/detailNav'

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
  <n-tooltip placement="top">
    <template #trigger>
      <n-button
        v-bind="$attrs"
        text
        class="score-detail-link"
        :class="{ 'has-score': hasScore }"
        :aria-label="FIXTURE_DETAIL_TOOLTIP"
        @click="$emit('click')"
      >
        {{ label }}
      </n-button>
    </template>
    {{ FIXTURE_DETAIL_TOOLTIP }}
  </n-tooltip>
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
