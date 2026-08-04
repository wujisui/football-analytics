import type { Directive } from 'vue'

import { containNestedWheel } from '@/utils/nestedScroll'

/** Bind wheel so inner overflow scrolls instead of the parent virtual list. */
export const vNestedScroll: Directive<HTMLElement> = {
  mounted(el) {
    el.style.overscrollBehavior = 'contain'
    el.addEventListener('wheel', containNestedWheel, { passive: false })
  },
  unmounted(el) {
    el.removeEventListener('wheel', containNestedWheel)
  },
}
