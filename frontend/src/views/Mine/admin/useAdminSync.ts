import { computed, readonly, ref } from 'vue'

import { fetchAdminTaskStatus, triggerScheduledFixturesSync } from '@/api/admin'
import { useFavoriteFixtures } from '@/composables/useFavoriteFixtures'
import { notifyError, notifySuccess } from '@/utils/globalNotify'

type SyncOutcome = { ok: boolean; at: number; detail: string }

// Module level: the batch keeps running while the user leaves /mine/admin,
// so the button state must survive component unmount.
const syncing = ref(false)
const lastOutcome = ref<SyncOutcome | null>(null)
let pollPromise: Promise<void> | null = null

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function formatTime(at: number) {
  return new Date(at).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function useAdminSync() {
  async function waitForCompletion() {
    if (pollPromise) return pollPromise
    pollPromise = (async () => {
      let failures = 0
      for (;;) {
        await delay(1500)
        let data: Awaited<ReturnType<typeof fetchAdminTaskStatus>>
        try {
          data = await fetchAdminTaskStatus()
          failures = 0
        } catch (err) {
          failures += 1
          if (failures >= 5) throw err
          continue
        }
        const task = data.active_tasks.scheduled_fixtures_sync
        if (!task || task.status === 'running') continue
        const ok = task.status === 'completed'
        const detail = task.error || `后端返回状态：${task.status}`
        lastOutcome.value = { ok, at: Date.now(), detail: ok ? '' : detail }
        syncing.value = false
        if (ok) {
          await refreshFavorites()
          notifySuccess('同步官方 API 数据完成', '赛程、盘口、赛果与自动推荐已更新')
        } else {
          notifyError('同步官方 API 数据未完成', detail)
        }
        return
      }
    })().finally(() => {
      pollPromise = null
    })
    return pollPromise
  }

  async function hydrateStatus() {
    try {
      const data = await fetchAdminTaskStatus()
      syncing.value =
        data.active_tasks.scheduled_fixtures_sync?.status === 'running'
      if (syncing.value) {
        void waitForCompletion().catch(() => {
          syncing.value = false
        })
      }
    } catch {
      // Admin page setting load reports authentication/network failures.
    }
  }

  const { refresh: refreshFavorites } = useFavoriteFixtures()

  const statusText = computed(() => {
    if (syncing.value) return '同步进行中，完成后会全局提示'
    const outcome = lastOutcome.value
    if (!outcome) return ''
    return outcome.ok
      ? `上次同步成功：${formatTime(outcome.at)}`
      : `上次同步失败（${formatTime(outcome.at)}）：${outcome.detail}`
  })

  async function runSync() {
    if (syncing.value) return
    syncing.value = true
    try {
      const data = await triggerScheduledFixturesSync()
      const task = data.task_status.active_tasks.scheduled_fixtures_sync
      if (task?.status === 'running' || data.status === 'accepted') {
        await waitForCompletion()
        return
      }
      const detail =
        task?.error ||
        (task ? `后端返回状态：${task.status}` : '后端未返回任务状态')
      lastOutcome.value = { ok: false, at: Date.now(), detail }
      notifyError('同步官方 API 数据未完成', detail)
    } catch (err) {
      const detail = err instanceof Error ? err.message : '请求失败'
      lastOutcome.value = { ok: false, at: Date.now(), detail }
      notifyError('同步官方 API 数据失败', detail)
    } finally {
      if (!pollPromise) syncing.value = false
    }
  }

  return {
    syncing: readonly(syncing),
    statusText,
    runSync,
    hydrateStatus,
  }
}
