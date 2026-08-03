import { onActivated, onBeforeUnmount, onDeactivated, onMounted, watch, type Ref } from 'vue'

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

function persist(key: string, top: number) {
  const map = allOffsets()
  if (top <= 0) delete map[key]
  else map[key] = top
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(map))
  } catch {
    /* private mode / quota — keep in-memory only */
  }
}

/**
 * Remember a list's scroll offset for the browser session.
 * Covers keep-alive deactivation and full page reloads (mobile tab discard).
 */
export function useScrollRestore(
  key: string,
  shell: Ref<HTMLElement | null>,
  options?: { enabled?: Ref<boolean> },
) {
  let bound: HTMLElement | null = null
  let frame = 0

  function container(): HTMLElement | null {
    return (
      (shell.value?.querySelector('.n-scrollbar-container') as HTMLElement | null) ?? null
    )
  }

  function onScroll() {
    if (!bound) return
    persist(key, bound.scrollTop)
  }

  function bind() {
    const el = container()
    if (!el || el === bound) return !!bound
    unbind()
    bound = el
    el.addEventListener('scroll', onScroll, { passive: true })
    return true
  }

  function unbind() {
    bound?.removeEventListener('scroll', onScroll)
    bound = null
  }

  function restore() {
    if (options?.enabled && !options.enabled.value) return
    const target = allOffsets()[key] ?? 0
    let attempts = RESTORE_ATTEMPTS
    cancelAnimationFrame(frame)

    const step = () => {
      const el = container()
      if (el) {
        bind()
        if (!target) return
        const max = el.scrollHeight - el.clientHeight
        if (max >= target) {
          el.scrollTop = target
          return
        }
        // List still rendering — hold the furthest reachable spot meanwhile.
        if (max > 0) el.scrollTop = max
      }
      if (--attempts > 0) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
  }

  function save() {
    if (bound) persist(key, bound.scrollTop)
  }

  /** New content (e.g. another day) — start from the top, drop the old offset. */
  function reset() {
    cancelAnimationFrame(frame)
    persist(key, 0)
    const el = container()
    if (el) el.scrollTop = 0
  }

  onMounted(restore)
  onActivated(restore)
  onDeactivated(() => {
    save()
    cancelAnimationFrame(frame)
    unbind()
  })
  onBeforeUnmount(() => {
    save()
    cancelAnimationFrame(frame)
    unbind()
  })

  // Shell mounts after an error/empty state resolves — rebind when it appears.
  watch(shell, (el) => {
    if (el) restore()
  })

  return { restore, save, reset }
}
