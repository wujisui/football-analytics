<script setup lang="ts">
import { computed } from 'vue'

import { useIsPhone } from '@/composables/useMediaQuery'
import { detailTabLabel, type DetailTab } from '@/utils/detailNav'

/**
 * 悬停提示：这块可点区域点进详情后默认落在哪个 tab。
 * 只做鼠标端；手机没有 hover，直接渲染原内容。
 */
const props = defineProps<{ tab: DetailTab }>()

const isPhone = useIsPhone()
const label = computed(() => detailTabLabel(props.tab))
</script>

<template>
  <n-tooltip
    :disabled="isPhone"
    trigger="hover"
    placement="top"
    :delay="200"
  >
    <template #trigger>
      <slot />
    </template>
    {{ label }}
  </n-tooltip>
</template>
