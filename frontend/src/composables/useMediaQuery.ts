import { onMounted, onUnmounted, ref, type Ref } from 'vue'

function readMatches(query: string): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  return window.matchMedia(query).matches
}

/** Reactive match for a CSS media query (e.g. `(max-width: 767px)`). */
export function useMediaQuery(query: string): Ref<boolean> {
  // Sync on create so first paint already knows phone vs desktop
  // (avoid briefly rendering desktop sider then removing it).
  const matches = ref(readMatches(query))
  let mql: MediaQueryList | null = null

  function sync() {
    matches.value = !!mql?.matches
  }

  onMounted(() => {
    mql = window.matchMedia(query)
    sync()
    mql.addEventListener('change', sync)
  })

  onUnmounted(() => {
    mql?.removeEventListener('change', sync)
    mql = null
  })

  return matches
}

/** Phone portrait / small devices — use drawer instead of fixed sider. */
export function useIsPhone() {
  return useMediaQuery('(max-width: 767px)')
}

/** Tablet and below — prefer collapsed sider / tighter padding. */
export function useIsTabletDown() {
  return useMediaQuery('(max-width: 1023px)')
}
