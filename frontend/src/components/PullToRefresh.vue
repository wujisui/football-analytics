<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { findScrollContainer } from '@/utils/scrollContainer'

const props = withDefaults(
  defineProps<{
    /** Scroll shell wrapping virtual-list / n-scrollbar — `position: relative`. */
    shell: HTMLElement | null
    refreshing?: boolean
    disabled?: boolean
  }>(),
  { refreshing: false, disabled: false },
)

const emit = defineEmits<{ refresh: [] }>()

const THRESHOLD = 56
const MAX_PULL = 88

const pullPx = ref(0)
const armed = ref(false)

let listenEl: HTMLElement | null = null
let startY = 0
let startX = 0
let tracking = false
let pulling = false

const label = computed(() => {
  if (props.refreshing) return '刷新中…'
  if (armed.value) return '释放刷新'
  if (pullPx.value > 8) return '下拉刷新'
  return ''
})

const indicatorHeight = computed(() =>
  props.refreshing ? 40 : Math.round(pullPx.value),
)

function scrollListenTo(shell: HTMLElement | null): HTMLElement | null {
  return findScrollContainer(shell)
}

function resetPull() {
  tracking = false
  pulling = false
  armed.value = false
  pullPx.value = 0
}

function onTouchStart(e: TouchEvent) {
  if (props.disabled || props.refreshing) return
  if (e.touches.length !== 1) return
  const el = listenEl
  if (!el || el.scrollTop > 0) return
  startY = e.touches[0].clientY
  startX = e.touches[0].clientX
  tracking = true
  pulling = false
  armed.value = false
  pullPx.value = 0
}

function onTouchMove(e: TouchEvent) {
  if (!tracking || props.disabled || props.refreshing) return
  const t = e.touches[0]
  const dy = t.clientY - startY
  const dx = t.clientX - startX

  if (!pulling) {
    // Let horizontal tab swipes win.
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10) {
      tracking = false
      return
    }
    if (dy < 8) return
    if (listenEl && listenEl.scrollTop > 0) {
      tracking = false
      return
    }
    pulling = true
  }

  if (dy <= 0) {
    pullPx.value = 0
    armed.value = false
    return
  }

  // Block browser overscroll while we own the gesture.
  e.preventDefault()
  const damped = Math.min(MAX_PULL, dy * 0.45)
  pullPx.value = damped
  armed.value = damped >= THRESHOLD
}

function onTouchEnd() {
  if (!tracking && !pulling) return
  const shouldRefresh = pulling && armed.value && !props.refreshing
  tracking = false
  pulling = false
  armed.value = false
  if (shouldRefresh) {
    pullPx.value = Math.min(pullPx.value, 40)
    emit('refresh')
    return
  }
  pullPx.value = 0
}

function detach() {
  if (!listenEl) return
  listenEl.removeEventListener('touchstart', onTouchStart)
  listenEl.removeEventListener('touchmove', onTouchMove)
  listenEl.removeEventListener('touchend', onTouchEnd)
  listenEl.removeEventListener('touchcancel', onTouchEnd)
  listenEl = null
}

function attach(shell: HTMLElement | null) {
  detach()
  const el = scrollListenTo(shell)
  if (!el) return
  listenEl = el
  el.addEventListener('touchstart', onTouchStart, { passive: true })
  el.addEventListener('touchmove', onTouchMove, { passive: false })
  el.addEventListener('touchend', onTouchEnd, { passive: true })
  el.addEventListener('touchcancel', onTouchEnd, { passive: true })
}

watch(
  () => props.shell,
  (shell) => {
    attach(shell)
    // n-scrollbar container may mount a tick after the shell ref.
    if (shell && !listenEl) {
      requestAnimationFrame(() => attach(shell))
    }
  },
  { immediate: true },
)

watch(
  () => props.refreshing,
  (busy, was) => {
    if (was && !busy) resetPull()
  },
)

onBeforeUnmount(() => {
  detach()
  resetPull()
})
</script>

<template>
  <div
    class="ptr-indicator"
    :class="{ active: indicatorHeight > 0 }"
    :style="{ height: `${indicatorHeight}px` }"
    aria-hidden="true"
  >
    <span v-if="label" class="ptr-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.ptr-indicator {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 4;
  overflow: hidden;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  pointer-events: none;
  background: transparent;
  transition: none;
}

.ptr-indicator.active {
  background: color-mix(in srgb, var(--fa-bg-elevated) 88%, transparent);
}

.ptr-label {
  padding: 0 0 8px;
  font-size: 12px;
  line-height: 1.2;
  color: var(--fa-text-muted);
  white-space: nowrap;
}
</style>
