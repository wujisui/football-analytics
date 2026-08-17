<script setup lang="ts">
import { computed } from 'vue'

import { normalizeQualityRating } from '@/utils/qualityRating'

const props = defineProps<{
  /** 0.5–5 星；无效或非推荐时不渲染。 */
  value?: number | null
}>()

const rating = computed(() => normalizeQualityRating(props.value))
</script>

<template>
  <n-rate
    v-if="rating != null"
    class="quality-rate"
    readonly
    allow-half
    :size="14"
    :count="5"
    :value="rating"
    :aria-label="`推荐质量 ${rating} / 5`"
  />
</template>

<style scoped>
.quality-rate {
  flex-shrink: 0;
  justify-self: end;
}
</style>
