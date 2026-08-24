<script setup lang="ts">
// `aria-label` 由调用方以普通属性透传到 n-switch 根节点，不再单开一个 prop。
withDefaults(
  defineProps<{
    value: boolean
    checkedText: string
    uncheckedText: string
    disabled?: boolean
    loading?: boolean
  }>(),
  { disabled: false, loading: false },
)

defineEmits<{ 'update:value': [boolean] }>()
</script>

<template>
  <n-switch
    class="text-switch"
    :value="value"
    :disabled="disabled"
    :loading="loading"
    @update:value="$emit('update:value', $event)"
  >
    <template #checked>{{ checkedText }}</template>
    <template #unchecked>{{ uncheckedText }}</template>
  </n-switch>
</template>

<style scoped>
/**
 * 轨道内的占位文案带 overflow:hidden，最小尺寸会塌到默认轨道宽，
 * 放进 n-list-item 的 suffix（flex: 0）时字会被裁掉，所以锁住内容宽度。
 */
.text-switch {
  flex: 0 0 auto;
  min-width: max-content;
}
</style>
