<script setup lang="ts">
import { HelpCircleOutline } from '@vicons/ionicons5'

import { useIsPhone } from '@/composables/useMediaQuery'

/**
 * 细则收进 `?`：列表默认只留一句短文案，想看完整规则再悬停。
 * 手机没有 hover，改成点击触发，否则移动端拿不到这段说明。
 */
defineProps<{ text: string }>()

const isPhone = useIsPhone()
</script>

<template>
  <n-tooltip
    :trigger="isPhone ? 'click' : 'hover'"
    placement="top"
    :delay="120"
    :style="{ maxWidth: '340px' }"
  >
    <template #trigger>
      <n-icon
        class="help-tip"
        :component="HelpCircleOutline"
        :size="15"
        role="button"
        tabindex="0"
        aria-label="查看完整说明"
      />
    </template>
    {{ text }}
  </n-tooltip>
</template>

<style scoped>
.help-tip {
  flex-shrink: 0;
  color: var(--fa-text-secondary);
  cursor: help;
  vertical-align: -2px;
}

.help-tip:hover,
.help-tip:focus-visible {
  color: var(--fa-text);
}
</style>
