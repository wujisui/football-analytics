import { toValue, type MaybeRefOrGetter } from 'vue'

const DEFAULT_THRESHOLD = 48

/**
 * Horizontal swipe → prev/next (phone tab panes).
 * Ignores mostly-vertical gestures and known horizontal pan targets (charts, etc.).
 */
export function useHorizontalSwipe(options: {
  enabled?: MaybeRefOrGetter<boolean>
  onSwipeLeft: () => void
  onSwipeRight: () => void
  threshold?: number
}) {
  const threshold = options.threshold ?? DEFAULT_THRESHOLD
  let startX = 0
  let startY = 0
  let tracking = false
  let blocked = false

  function isBlockedTarget(target: EventTarget | null): boolean {
    if (!(target instanceof Element)) return false
    return !!target.closest(
      '.echarts, canvas, [data-no-tab-swipe], .n-data-table-base-table-header',
    )
  }

  function onTouchStart(e: TouchEvent) {
    if (!toValue(options.enabled ?? true)) return
    if (e.touches.length !== 1) return
    blocked = isBlockedTarget(e.target)
    if (blocked) {
      tracking = false
      return
    }
    const t = e.touches[0]
    startX = t.clientX
    startY = t.clientY
    tracking = true
  }

  function onTouchMove(e: TouchEvent) {
    if (!tracking || blocked) return
    // Once clearly vertical, abort so nested scroll keeps control.
    const t = e.touches[0]
    const dx = t.clientX - startX
    const dy = t.clientY - startY
    if (Math.abs(dy) > Math.abs(dx) && Math.abs(dy) > 12) {
      tracking = false
    }
  }

  function onTouchEnd(e: TouchEvent) {
    if (!tracking || blocked) {
      tracking = false
      blocked = false
      return
    }
    tracking = false
    if (!toValue(options.enabled ?? true)) return
    const t = e.changedTouches[0]
    const dx = t.clientX - startX
    const dy = t.clientY - startY
    if (Math.abs(dx) < threshold || Math.abs(dx) < Math.abs(dy)) return
    if (dx < 0) options.onSwipeLeft()
    else options.onSwipeRight()
  }

  function onTouchCancel() {
    tracking = false
    blocked = false
  }

  return { onTouchStart, onTouchMove, onTouchEnd, onTouchCancel }
}
