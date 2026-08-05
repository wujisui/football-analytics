<script setup lang="ts">
import { ArrowDownOutline, ArrowUpOutline } from '@vicons/ionicons5'
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { useIsPhone } from '@/composables/useMediaQuery'
import { findScrollContainer } from '@/utils/scrollContainer'

const props = withDefaults(
  defineProps<{
    /** Primary scroll shell wrapping virtual-list / n-scrollbar. */
    shell: HTMLElement | null
    /** Extra shell scrolled together (e.g. desktop odds column). */
    syncShell?: HTMLElement | null
    visibilityHeight?: number
    right?: number
    bottom?: number
  }>(),
  {
    syncShell: null,
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

const showTop = ref(false)
const showBottom = ref(false)
const showGroup = computed(() => showTop.value || showBottom.value)

let listenEl: HTMLElement | null = null
let resizeObserver: ResizeObserver | null = null
let mutationObserver: MutationObserver | null = null
let visibilityRaf = 0

function scrollTargets(): HTMLElement[] {
  const targets: HTMLElement[] = []
  for (const shell of [props.shell, props.syncShell]) {
    if (!shell) continue
    const el = findScrollContainer(shell)
    if (el) targets.push(el)
  }
  return targets
}

function updateVisibility() {
  const el = listenEl
  if (!el) {
    showTop.value = false
    showBottom.value = false
    return
  }
  showTop.value = el.scrollTop > props.visibilityHeight
  const gap = el.scrollHeight - el.scrollTop - el.clientHeight
  showBottom.value = gap > props.visibilityHeight
}

function scheduleVisibility() {
  if (visibilityRaf) return
  visibilityRaf = requestAnimationFrame(() => {
    visibilityRaf = 0
    updateVisibility()
  })
}

function scrollToTop() {
  for (const el of scrollTargets()) {
    el.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

function scrollToBottom() {
  for (const el of scrollTargets()) {
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }
}

function bindListenEl(el: HTMLElement | null) {
  if (listenEl) {
    listenEl.removeEventListener('scroll', scheduleVisibility)
  }
  resizeObserver?.disconnect()
  resizeObserver = null
  listenEl = el
  if (!el) {
    showTop.value = false
    showBottom.value = false
    return
  }
  el.addEventListener('scroll', scheduleVisibility, { passive: true })
  resizeObserver = new ResizeObserver(scheduleVisibility)
  resizeObserver.observe(el)
  const content = el.firstElementChild
  if (content) resizeObserver.observe(content)
  updateVisibility()
}

function detach() {
  if (listenEl) {
    listenEl.removeEventListener('scroll', scheduleVisibility)
  }
  resizeObserver?.disconnect()
  resizeObserver = null
  mutationObserver?.disconnect()
  mutationObserver = null
  listenEl = null
  if (visibilityRaf) {
    cancelAnimationFrame(visibilityRaf)
    visibilityRaf = 0
  }
  showTop.value = false
  showBottom.value = false
}

function attach(shell: HTMLElement | null) {
  detach()
  if (!shell) return

  // Virtual list mounts/unmounts with empty↔data; keep watching the shell.
  mutationObserver = new MutationObserver(() => {
    const next = findScrollContainer(shell)
    if (next !== listenEl) bindListenEl(next)
  })
  mutationObserver.observe(shell, { childList: true, subtree: true })
  bindListenEl(findScrollContainer(shell))
  // n-virtual-list may mount a tick after the shell ref.
  if (!listenEl) {
    requestAnimationFrame(() => {
      if (props.shell === shell) bindListenEl(findScrollContainer(shell))
    })
  }
}

watch(
  () => props.shell,
  (shell) => attach(shell),
  { immediate: true },
)

onBeforeUnmount(detach)
</script>

<template>
  <transition name="list-scroll-fab">
    <div
      v-if="shell && showGroup"
      class="list-scroll-fab-group"
      :class="{ 'has-both': showTop && showBottom }"
      :style="{ right: `${right}px`, bottom: `${contentBottom}px` }"
    >
      <button
        v-if="showTop"
        type="button"
        class="list-scroll-fab"
        aria-label="回到顶部"
        @click="scrollToTop"
      >
        <n-icon :component="ArrowUpOutline" :size="20" />
      </button>
      <button
        v-if="showBottom"
        type="button"
        class="list-scroll-fab"
        aria-label="滚到底部"
        @click="scrollToBottom"
      >
        <n-icon :component="ArrowDownOutline" :size="20" />
      </button>
    </div>
  </transition>
</template>

<style scoped>
.list-scroll-fab-group {
  position: absolute;
  z-index: 5;
  display: inline-flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
  background: var(--fa-bg-elevated, #333);
}

.list-scroll-fab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  cursor: pointer;
  color: var(--fa-text-strong, #fff);
  background: transparent;
}

.list-scroll-fab-group.has-both .list-scroll-fab + .list-scroll-fab {
  border-top: 1px solid var(--fa-border, rgba(255, 255, 255, 0.12));
}

.list-scroll-fab:hover,
.list-scroll-fab:focus-visible {
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
