<script setup lang="ts">
withDefaults(
  defineProps<{
    /** Scroll shell wrapping `n-scrollbar` — must be `position: relative`. */
    shell: HTMLElement | null
    visibilityHeight?: number
    right?: number
    bottom?: number
  }>(),
  {
    visibilityHeight: 240,
    right: 16,
    bottom: 20,
  },
)

function scrollListenTo(shell: HTMLElement | null): HTMLElement {
  return (
    (shell?.querySelector('.n-scrollbar-container') as HTMLElement | null) ??
    document.documentElement
  )
}
</script>

<template>
  <n-back-top
    v-if="shell"
    class="list-back-top"
    :to="shell"
    :listen-to="() => scrollListenTo(shell)"
    :visibility-height="visibilityHeight"
    :right="right"
    :bottom="bottom"
  />
</template>

<style scoped>
.list-back-top {
  position: absolute !important;
}
</style>
