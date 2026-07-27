<script setup lang="ts">
import { FIXTURE_DETAIL_TOOLTIP } from '@/utils/detailNav'

defineOptions({ inheritAttrs: false })

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
      <n-button
        v-bind="$attrs"
        text
        class="score-detail-link"
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

.score-detail-link:hover {
  color: var(--fa-highlight-text);
}
</style>
