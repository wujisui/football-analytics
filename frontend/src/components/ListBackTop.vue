<script setup lang="ts">
import { ArrowDownOutline, ArrowUpOutline } from '@vicons/ionicons5'
import {
  computed,
  nextTick,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  ref,
  watch,
} from 'vue'

import { useIsPhone } from '@/composables/useMediaQuery'
import { findScrollContainer } from '@/utils/scrollContainer'

const props = withDefaults(
  defineProps<{
    /** Primary scroll shell wrapping virtual-list / n-scrollbar. */
    shell: HTMLElement | null
    visibilityHeight?: number
    right?: number
    bottom?: number
    /** Rebind when empty/data or list implementations switch. */
    contentKey?: string | number
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

const showTop = ref(false)
const showBottom = ref(false)
const showGroup = computed(() => showTop.value || showBottom.value)

let listenEl: HTMLElement | null = null
let resizeObserver: ResizeObserver | null = null
let visibilityRaf = 0
let attachRaf = 0
let active = true

function scrollTargets(): HTMLElement[] {
  const el = findScrollContainer(props.shell)
  return el ? [el] : []
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
  listenEl = null
  if (attachRaf) {
    cancelAnimationFrame(attachRaf)
    attachRaf = 0
  }
  if (visibilityRaf) {
    cancelAnimationFrame(visibilityRaf)
    visibilityRaf = 0
  }
  showTop.value = false
  showBottom.value = false
}

function attach(shell: HTMLElement | null) {
  detach()
  if (!active || !shell) return
  bindListenEl(findScrollContainer(shell))
}

function scheduleAttach() {
  const shell = props.shell
  if (!active || !shell) return
  void nextTick(() => {
    if (!active || props.shell !== shell) return
    attach(shell)
    // Virtual list may mount one frame after the shell/content switch.
    if (!listenEl) {
      attachRaf = requestAnimationFrame(() => {
        attachRaf = 0
        if (active && props.shell === shell) attach(shell)
      })
    }
  })
}

watch(
  () => [props.shell, props.contentKey] as const,
  scheduleAttach,
  { immediate: true },
)

onActivated(() => {
  active = true
  scheduleAttach()
})
onDeactivated(() => {
  active = false
  detach()
})
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
  background: var(--fa-bg-elevated);
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
  color: var(--fa-text-strong);
  background: transparent;
}

.list-scroll-fab-group.has-both .list-scroll-fab + .list-scroll-fab {
  border-top: 1px solid var(--fa-border);
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
