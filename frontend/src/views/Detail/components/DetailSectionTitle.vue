<script setup lang="ts">
/** 详情页区块色带标题。右侧 `extra` 插槽放场次选择、来源说明等同行控件。 */
defineProps<{ title: string }>()
</script>

<template>
  <n-flex class="section-band" justify="space-between" align="center" :size="12">
    <n-flex align="center" :size="8">
      <span class="title-bar" aria-hidden="true" />
      <n-text strong class="band-title">{{ title }}</n-text>
    </n-flex>
    <slot name="extra" />
  </n-flex>
</template>

<style scoped>
.section-band {
  padding: 10px 12px;
  background: var(--fa-bg-soft);
}

.title-bar {
  width: 3px;
  height: 14px;
  border-radius: 1px;
  background: var(--fa-wdl-win);
  flex-shrink: 0;
}

.band-title {
  font-size: 15px;
}
</style>
