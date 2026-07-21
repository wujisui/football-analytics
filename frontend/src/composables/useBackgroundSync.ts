import { ref } from 'vue'
import { createDiscreteApi } from 'naive-ui'

import {
  fetchSyncStatus,
  syncFixtures,
  type SyncFixturesOptions,
} from '@/api/fixtures'

const { message } = createDiscreteApi(['message'])

const POLL_MS = 2500

let pollTimer: ReturnType<typeof setInterval> | null = null
let pollCallbacks: Array<(ok: boolean) => void> = []
const backgroundActive = ref(false)

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  backgroundActive.value = false
}

function settlePoll(ok: boolean) {
  const callbacks = pollCallbacks.slice()
  pollCallbacks = []
  stopPoll()
  for (const cb of callbacks) cb(ok)
}

function startPoll(onSettled: (ok: boolean) => void) {
  pollCallbacks.push(onSettled)
  if (pollTimer) return

  backgroundActive.value = true
  const tick = async () => {
    try {
      const status = await fetchSyncStatus()
      if (status.running) return
      if (status.last_status === 'ok') {
        settlePoll(true)
      } else {
        message.error(
          status.last_error || status.last_message || '官方数据同步失败',
        )
        settlePoll(false)
      }
    } catch {
      message.error('同步状态查询失败')
      settlePoll(false)
    }
  }

  void tick()
  pollTimer = setInterval(() => void tick(), POLL_MS)
}

/** Fire-and-forget official sync; poll until idle then invoke ``onSettled``. */
export function enqueueBackgroundSync(
  options: SyncFixturesOptions,
  onSettled: (ok: boolean) => void,
): void {
  void (async () => {
    try {
      const res = await syncFixtures({ ...options, background: true })
      if (res.status === 'accepted' || res.status === 'running') {
        startPoll(onSettled)
        return
      }
      if (res.status === 'ok') {
        onSettled(true)
        return
      }
      message.error(res.message || '同步失败')
      onSettled(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '同步失败')
      onSettled(false)
    }
  })()
}

export function useBackgroundSync() {
  return { backgroundActive }
}

export function teardownBackgroundSyncPoll() {
  pollCallbacks = []
  stopPoll()
}
