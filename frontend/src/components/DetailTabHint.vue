<script setup lang="ts">
import { computed } from 'vue'

import { useIsPhone } from '@/composables/useMediaQuery'
import { detailTabLabel, type DetailTab } from '@/utils/detailNav'

/**
 * 悬停提示：这块可点区域点进详情后默认落在哪个 tab。
 * 只做鼠标端；手机没有 hover，直接渲染原内容。
 *
 * `text` 给内部有 `n-ellipsis` 的可点区域用：同一次 hover 只能有一个浮层，
 * 触发区自己的省略号浮层要关掉，被截断的全文改由这里显示，并取代 tab 名。
 */
const props = defineProps<{ tab: DetailTab; text?: string }>()

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
    {{ text || label }}
  </n-tooltip>
</template>
