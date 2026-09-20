<script setup lang="ts">
import { computed } from 'vue'

import { normalizeQualityRating } from '@/utils/qualityRating'

const props = defineProps<{
  /** 0.5–5 星；无效或非推荐时不渲染。 */
  value?: number | null
  /** 非推荐场次也占住同样宽度，供固定分栏的行对齐。 */
  reserveSpace?: boolean
}>()

const rating = computed(() => normalizeQualityRating(props.value))
const placeholder = computed(() => rating.value == null)
</script>

<template>
  <n-rate
    v-if="!placeholder || reserveSpace"
    class="quality-rate"
    :class="{ placeholder }"
    readonly
    allow-half
    :size="14"
    :count="5"
    :value="rating ?? 0"
    :aria-hidden="placeholder ? 'true' : undefined"
    :aria-label="placeholder ? undefined : `推荐质量 ${rating} / 5`"
  />
</template>

<style scoped>
.quality-rate {
  flex-shrink: 0;
}

.quality-rate.placeholder {
  visibility: hidden;
}
</style>
