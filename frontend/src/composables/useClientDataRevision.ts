import { fetchClientDataRevision } from '@/api/fixtures'
import { useFavoriteFixtures } from '@/composables/useFavoriteFixtures'
import { invalidatePrematchListCache } from '@/composables/useHomeFixtures'
import { invalidateFinishedResultsCache } from '@/composables/useResultsLeagues'

let remoteRevision: string | null = null
let syncPromise: Promise<void> | null = null

/** Drop list caches and reload picks. Pages in the foreground watch the epoch. */
export async function notifyLocalDataChanged(): Promise<void> {
  invalidatePrematchListCache()
  invalidateFinishedResultsCache()
  await useFavoriteFixtures().refresh()
}

async function syncFromServer(): Promise<void> {
  if (syncPromise) return syncPromise
  syncPromise = (async () => {
    const next = await fetchClientDataRevision()
    const changed = remoteRevision != null && next !== remoteRevision
    remoteRevision = next
    if (changed) await notifyLocalDataChanged()
  })().finally(() => {
    syncPromise = null
  })
  return syncPromise
}

const VISIBLE_POLL_MS = 30_000

/** 【比赛】/【赛果】在前台时才读本地版本。锁屏或离开这两页即停表。 */
export function startClientDataRevisionMonitor(): () => void {
  let timer = 0
  const poll = () => {
    void syncFromServer().catch(() => undefined)
  }
  const stopTimer = () => {
    if (!timer) return
    window.clearInterval(timer)
    timer = 0
  }
  const onVisibility = () => {
    if (document.visibilityState !== 'visible') {
      stopTimer()
      return
    }
    poll()
    if (!timer) timer = window.setInterval(poll, VISIBLE_POLL_MS)
  }
  onVisibility()
  document.addEventListener('visibilitychange', onVisibility)
  window.addEventListener('pageshow', onVisibility)
  return () => {
    stopTimer()
    document.removeEventListener('visibilitychange', onVisibility)
    window.removeEventListener('pageshow', onVisibility)
  }
}
