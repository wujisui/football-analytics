<script setup lang="ts">
defineProps<{
  rootLabel: string
  filterLabel: string
}>()

const emit = defineEmits<{
  selectRoot: []
}>()
</script>

<template>
  <n-breadcrumb class="fa-toolbar-crumb">
    <n-breadcrumb-item @click="emit('selectRoot')">{{ rootLabel }}</n-breadcrumb-item>
    <n-breadcrumb-item>{{ filterLabel }}</n-breadcrumb-item>
  </n-breadcrumb>
</template>
