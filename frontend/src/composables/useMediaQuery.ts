import { ref, type Ref } from 'vue'

const sharedQueries = new Map<string, Ref<boolean>>()
const sharedListeners = new Map<
  string,
  { mql: MediaQueryList; sync: () => void }
>()

function readMatches(query: string): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  return window.matchMedia(query).matches
}

/** Reactive match for a CSS media query (e.g. `(max-width: 767px)`). */
export function useMediaQuery(query: string): Ref<boolean> {
  const existing = sharedQueries.get(query)
  if (existing) return existing

  // One MediaQueryList per query for the whole app. Card-heavy lists call
  // useIsPhone many times; per-component listeners otherwise stay alive with
  // keep-alive and multiply resize work.
  const matches = ref(readMatches(query))
  sharedQueries.set(query, matches)
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return matches
  }

  const mql = window.matchMedia(query)
  const sync = () => {
    matches.value = mql.matches
  }
  sync()
  mql.addEventListener('change', sync)
  sharedListeners.set(query, { mql, sync })

  return matches
}

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    for (const { mql, sync } of sharedListeners.values()) {
      mql.removeEventListener('change', sync)
    }
    sharedListeners.clear()
    sharedQueries.clear()
  })
}

/** Phone portrait / small devices — use drawer instead of fixed sider. */
export function useIsPhone() {
  return useMediaQuery('(max-width: 767px)')
}

/** Tablet and below — prefer collapsed sider / tighter padding. */
export function useIsTabletDown() {
  return useMediaQuery('(max-width: 1023px)')
}
