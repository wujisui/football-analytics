<script setup lang="ts">
import { ArrowDownOutline } from '@vicons/ionicons5'
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { useIsPhone } from '@/composables/useMediaQuery'

const props = withDefaults(
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

const isPhone = useIsPhone()
/** Keep clear of the fixed bottom route bar on phones. */
const contentBottom = computed(() =>
  isPhone.value ? Math.max(props.bottom, 72) : props.bottom,
)
/** Sit above the back-top control. */
const bottomBtnOffset = computed(() => contentBottom.value + 52)

const showBottom = ref(false)

let listenEl: HTMLElement | null = null
let resizeObserver: ResizeObserver | null = null
let visibilityRaf = 0

function scrollListenTo(shell: HTMLElement | null): HTMLElement | null {
  if (!shell) return null
  return (
    (shell.querySelector('.n-scrollbar-container') as HTMLElement | null) ??
    shell
  )
}

function backTopListenTo(): HTMLElement {
  return scrollListenTo(props.shell) ?? document.documentElement
}

function updateBottomVisibility() {
  const el = listenEl
  if (!el) {
    showBottom.value = false
    return
  }
  const gap = el.scrollHeight - el.scrollTop - el.clientHeight
  showBottom.value = gap > props.visibilityHeight
}

/** Coalesce scroll + resize into one layout read per frame. */
function scheduleBottomVisibility() {
  if (visibilityRaf) return
  visibilityRaf = requestAnimationFrame(() => {
    visibilityRaf = 0
    updateBottomVisibility()
  })
}

function scrollToBottom() {
  listenEl?.scrollTo({ top: listenEl.scrollHeight, behavior: 'smooth' })
}

function detach() {
  if (listenEl) {
    listenEl.removeEventListener('scroll', scheduleBottomVisibility)
  }
  resizeObserver?.disconnect()
  resizeObserver = null
  listenEl = null
  if (visibilityRaf) {
    cancelAnimationFrame(visibilityRaf)
    visibilityRaf = 0
  }
  showBottom.value = false
}

function attach(shell: HTMLElement | null) {
  detach()
  const el = scrollListenTo(shell)
  if (!shell || !el) return
  listenEl = el
  el.addEventListener('scroll', scheduleBottomVisibility, { passive: true })
  resizeObserver = new ResizeObserver(scheduleBottomVisibility)
  resizeObserver.observe(el)
  // List grows/shrinks without a scroll event (day switch, filter) — track content too.
  const content = el.firstElementChild
  if (content) resizeObserver.observe(content)
  updateBottomVisibility()
}

watch(
  () => props.shell,
  (shell) => attach(shell),
  { immediate: true },
)

onBeforeUnmount(detach)
</script>

<template>
  <template v-if="shell">
    <transition name="list-scroll-fab">
      <button
        v-show="showBottom"
        type="button"
        class="list-back-bottom"
        :style="{ right: `${right}px`, bottom: `${bottomBtnOffset}px` }"
        aria-label="滚到底部"
        @click="scrollToBottom"
      >
        <n-icon :component="ArrowDownOutline" :size="20" />
      </button>
    </transition>

    <n-back-top
      class="list-back-top"
      :to="shell"
      :listen-to="backTopListenTo"
      :visibility-height="visibilityHeight"
      :right="right"
      :bottom="contentBottom"
    />
  </template>
</template>

<style scoped>
.list-back-top,
.list-back-bottom {
  position: absolute !important;
  z-index: 5;
}

.list-back-bottom {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: 20px;
  cursor: pointer;
  color: var(--fa-text-strong, #fff);
  background: var(--fa-bg-elevated, #333);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}

.list-back-bottom:hover,
.list-back-bottom:focus-visible {
  outline: none;
  filter: brightness(1.08);
}

.list-scroll-fab-enter-active,
.list-scroll-fab-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.list-scroll-fab-enter-from,
.list-scroll-fab-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
