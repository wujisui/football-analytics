import { toValue, type MaybeRefOrGetter } from 'vue'

const DEFAULT_THRESHOLD = 48

/**
 * Horizontal swipe → prev/next (phone tab panes).
 * Ignores mostly-vertical gestures and gestures that start inside a horizontally
 * scrollable area (data tables, charts, badge rows).
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

  /** 起点落在横向可滚动区域（表格、徽标行）时让它自己滚，不翻页。 */
  function pansHorizontally(el: Element): boolean {
    if (el.scrollWidth - el.clientWidth <= 1) return false
    const overflowX = getComputedStyle(el).overflowX
    return overflowX === 'auto' || overflowX === 'scroll'
  }

  function isBlockedTarget(
    target: EventTarget | null,
    root: EventTarget | null,
  ): boolean {
    if (!(target instanceof Element)) return false
    // 数据表头由 Naive 跟随表体程序化滚动，自身 overflow 为 hidden，只能按类名拦。
    if (
      target.closest(
        '.echarts, canvas, [data-no-tab-swipe], .n-data-table-base-table-header',
      )
    ) {
      return true
    }
    const boundary = root instanceof Element ? root : null
    for (let el: Element | null = target; el && el !== boundary; el = el.parentElement) {
      if (pansHorizontally(el)) return true
    }
    return false
  }

  function onTouchStart(e: TouchEvent) {
    if (!toValue(options.enabled ?? true)) return
    if (e.touches.length !== 1) return
    blocked = isBlockedTarget(e.target, e.currentTarget)
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
