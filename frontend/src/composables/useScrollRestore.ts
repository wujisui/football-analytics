import {
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  watch,
  type Ref,
} from 'vue'

const STORAGE_KEY = 'fa-scroll-offsets'
/** Content arrives after the list request settles; retry until it fits. */
const RESTORE_ATTEMPTS = 40

let offsets: Record<string, number> | null = null

function allOffsets(): Record<string, number> {
  if (offsets) return offsets
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    offsets = raw ? (JSON.parse(raw) as Record<string, number>) : {}
  } catch {
    offsets = {}
  }
  return offsets
}

function writeStorage() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(allOffsets()))
  } catch {
    /* private mode / quota — keep in-memory only */
  }
}

function remember(key: string, top: number) {
  const map = allOffsets()
  if (top <= 0) {
    if (!(key in map)) return false
    delete map[key]
    return true
  }
  if (map[key] === top) return false
  map[key] = top
  return true
}

/**
 * Restore list scroll after remount / keep-alive / mobile tab discard.
 *
 * Does **not** write storage while scrolling. Position is read once when the
 * page is left (route leave, keep-alive deactivate, or app background /
 * tab discard via `pagehide`) — that is enough for “switch app and come back”.
 * While the WebView stays alive, the browser already keeps the scrollport.
 */
export function useScrollRestore(
  key: string,
  shell: Ref<HTMLElement | null>,
  options?: { enabled?: Ref<boolean> },
) {
  let bound: HTMLElement | null = null
  let frame = 0
  let abortInput: (() => void) | null = null

  function container(): HTMLElement | null {
    return (
      (shell.value?.querySelector('.n-scrollbar-container') as HTMLElement | null) ??
      null
    )
  }

  function bind() {
    const el = container()
    if (!el) return false
    bound = el
    return true
  }

  function unbind() {
    bound = null
  }

  function save() {
    const el = bound ?? container()
    if (!el) return
    bound = el
    if (remember(key, el.scrollTop)) writeStorage()
  }

  /** Stop restoring: writing scrollTop while the user scrolls looks like jitter. */
  function stopRestore() {
    cancelAnimationFrame(frame)
    frame = 0
    abortInput?.()
    abortInput = null
  }

  function watchUserInput() {
    abortInput?.()
    const events = ['wheel', 'touchstart', 'keydown'] as const
    const onInput = () => stopRestore()
    for (const type of events) {
      window.addEventListener(type, onInput, { passive: true })
    }
    abortInput = () => {
      for (const type of events) window.removeEventListener(type, onInput)
    }
  }

  function restore() {
    if (options?.enabled && !options.enabled.value) return
    const target = allOffsets()[key] ?? 0
    let attempts = RESTORE_ATTEMPTS
    stopRestore()
    if (!target) {
      bind()
      return
    }
    watchUserInput()

    const step = () => {
      const el = container()
      if (el) {
        bind()
        const max = el.scrollHeight - el.clientHeight
        if (max >= target) {
          el.scrollTop = target
          stopRestore()
          return
        }
        // List still rendering — hold the furthest reachable spot meanwhile.
        if (max > 0) el.scrollTop = max
      }
      if (--attempts > 0) frame = requestAnimationFrame(step)
      else stopRestore()
    }
    frame = requestAnimationFrame(step)
  }

  /** New content (e.g. another day) — start from the top, drop the old offset. */
  function reset() {
    stopRestore()
    if (remember(key, 0)) writeStorage()
    const el = container()
    if (el) el.scrollTop = 0
  }

  function onPageHide() {
    save()
  }

  onMounted(() => {
    restore()
    window.addEventListener('pagehide', onPageHide)
  })
  onActivated(restore)
  onDeactivated(() => {
    save()
    stopRestore()
    unbind()
  })
  onBeforeUnmount(() => {
    save()
    window.removeEventListener('pagehide', onPageHide)
    stopRestore()
    unbind()
  })

  // Shell mounts after an error/empty state resolves — rebind when it appears.
  watch(shell, (el) => {
    if (el) restore()
  })

  return { restore, save, reset }
}
