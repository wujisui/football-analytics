<script setup lang="ts">
import { computed } from 'vue'

import { useHandicapRuleset } from '@/composables/useHandicapRuleset'

const { ruleset, setRuleset } = useHandicapRuleset()

const isJc = computed(() => ruleset.value === 'jc')

function onUpdate(value: boolean) {
  setRuleset(value ? 'jc' : 'asian')
}
</script>

<template>
  <n-switch
    class="handicap-ruleset-switch"
    :value="isJc"
    size="medium"
    aria-label="让球玩法"
    @update:value="onUpdate"
  >
    <template #checked>竞彩</template>
    <template #unchecked>亚盘</template>
  </n-switch>
</template>

<style scoped>
/**
 * 轨道内的占位文案带 overflow:hidden，最小尺寸会塌到默认轨道宽，
 * 放进 n-list-item 的 suffix（flex: 0）时字会被裁掉，所以锁住内容宽度。
 */
.handicap-ruleset-switch {
  flex: 0 0 auto;
  min-width: max-content;
}
</style>
