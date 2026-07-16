<script setup lang="ts">
import { SearchOutline } from '@vicons/ionicons5'

const model = defineModel<string>({ default: '' })

withDefaults(
  defineProps<{
    placeholder?: string
  }>(),
  { placeholder: '搜索俱乐部' },
)
</script>

<template>
  <n-input
    v-model:value="model"
    class="fa-toolbar-search"
    size="small"
    :placeholder="placeholder"
    clearable
  >
    <template #prefix>
      <n-icon :component="SearchOutline" :size="14" />
    </template>
  </n-input>
</template>
