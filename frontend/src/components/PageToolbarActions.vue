<script setup lang="ts">
const date = defineModel<string | null>('date', { default: null })

withDefaults(
  defineProps<{
    showDate?: boolean
    dateClearable?: boolean
    datePlaceholder?: string
    isDateDisabled?: (timestamp: number) => boolean
  }>(),
  {
    showDate: true,
    dateClearable: false,
    datePlaceholder: '',
    isDateDisabled: undefined,
  },
)
</script>

<template>
  <div class="fa-toolbar-actions">
    <n-date-picker
      v-if="showDate"
      v-model:formatted-value="date"
      class="fa-toolbar-date"
      value-format="yyyy-MM-dd"
      type="date"
      size="small"
      :clearable="dateClearable"
      :placeholder="datePlaceholder || undefined"
      :is-date-disabled="isDateDisabled"
    />
  </div>
</template>
