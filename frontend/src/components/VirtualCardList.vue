<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    items: ReadonlyArray<Record<string, unknown>>
    /** Row height. Prefer fixed size + `itemResizable=false` for heavy lists. */
    itemSize?: number
    /** ResizeObserver per row — costly when cards are heavy; keep off if heights are fixed. */
    itemResizable?: boolean
    keyField?: string
    paddingTop?: number | string
    paddingBottom?: number | string
    itemsStyle?: string | Record<string, string>
    showScrollbar?: boolean
  }>(),
  {
    itemSize: 160,
    itemResizable: true,
    keyField: 'key',
    paddingTop: 0,
    paddingBottom: 0,
    showScrollbar: true,
  },
)

</script>

<template>
  <n-virtual-list
    class="virtual-card-list"
    :items="props.items as Record<string, unknown>[]"
    :item-size="itemSize"
    :item-resizable="itemResizable"
    :key-field="keyField"
    :padding-top="paddingTop"
    :padding-bottom="paddingBottom"
    :items-style="itemsStyle"
    :show-scrollbar="showScrollbar"
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
