<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    items: ReadonlyArray<Record<string, unknown>>
    /** Initial estimate; `item-resizable` measures real card height. */
    itemSize?: number
    keyField?: string
    paddingTop?: number | string
    paddingBottom?: number | string
    itemsStyle?: string | Record<string, string>
  }>(),
  {
    itemSize: 160,
    keyField: 'key',
    paddingTop: 0,
    paddingBottom: 0,
  },
)

const emit = defineEmits<{
  scroll: [event: Event]
}>()

/** Naive VirtualList takes `onScroll` as a prop; @scroll maps to it. */
function onScroll(event: Event) {
  emit('scroll', event)
}
</script>

<template>
  <n-virtual-list
    class="virtual-card-list"
    :items="props.items as Record<string, unknown>[]"
    :item-size="itemSize"
    item-resizable
    :key-field="keyField"
    :padding-top="paddingTop"
    :padding-bottom="paddingBottom"
    :items-style="itemsStyle"
    @scroll="onScroll"
  >
    <template #default="slotProps">
      <slot v-bind="slotProps" />
    </template>
  </n-virtual-list>
</template>

<style scoped>
.virtual-card-list {
  height: 100%;
  min-height: 0;
}
</style>
