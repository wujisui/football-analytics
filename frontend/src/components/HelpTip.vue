<script setup lang="ts">
import { HelpCircleOutline } from '@vicons/ionicons5'
import { ref } from 'vue'

import { useIsPhone } from '@/composables/useMediaQuery'

/**
 * 细则收进 `?`：列表默认只留一句短文案，想看完整规则再悬停。
 * 手机没有 hover，且贴着屏幕右缘的图标会把气泡挤出视口，改为点开居中模态。
 */
defineProps<{ text: string }>()

const isPhone = useIsPhone()
const showDetail = ref(false)

function onTriggerClick() {
  if (isPhone.value) showDetail.value = true
}
</script>

<template>
  <n-tooltip
    :disabled="isPhone"
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
        @click="onTriggerClick"
        @keydown.enter="onTriggerClick"
      />
    </template>
    <span class="help-text">{{ text }}</span>
  </n-tooltip>

  <n-modal
    v-if="isPhone"
    v-model:show="showDetail"
    preset="card"
    title="说明"
    to="body"
    :auto-focus="false"
    :bordered="false"
    :style="{
      width: 'min(360px, calc(100vw - 32px))',
      maxHeight: 'calc(100dvh - 48px)',
      margin: 'auto',
    }"
  >
    <n-text depth="1" class="help-text" style="line-height: 1.6;">{{ text }}</n-text>
  </n-modal>
</template>

<style scoped>
/* 文案用换行分段，`?` 里逐条列而不是一大坨。 */
.help-text {
  white-space: pre-line;
}

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
