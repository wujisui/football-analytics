<script setup lang="ts">
import { FIXTURE_DETAIL_TOOLTIP } from '@/utils/detailNav'

defineProps<{
  label: string
}>()

defineEmits<{
  click: []
}>()
</script>

<template>
  <n-tooltip placement="top">
    <template #trigger>
      <button
        type="button"
        class="score-detail-link"
        :aria-label="FIXTURE_DETAIL_TOOLTIP"
        @click="$emit('click')"
      >
        {{ label }}
      </button>
    </template>
    {{ FIXTURE_DETAIL_TOOLTIP }}
  </n-tooltip>
</template>

<style scoped>
.score-detail-link {
  appearance: none;
  margin: 0;
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
  transition: color 0.15s ease;
}

.score-detail-link:hover {
  color: var(--fa-highlight-text);
}

.score-detail-link:focus-visible {
  outline: 2px solid var(--fa-highlight-border);
  outline-offset: 2px;
  border-radius: 2px;
}
</style>
