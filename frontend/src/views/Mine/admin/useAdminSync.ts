import { computed, readonly, ref } from 'vue'

import {
  fetchAdminTaskStatus,
  triggerScheduledFixturesSync,
  triggerScheduledResultsSync,
} from '@/api/admin'
import { useFavoriteFixtures } from '@/composables/useFavoriteFixtures'
import { notifyError, notifySuccess } from '@/utils/globalNotify'

const FULL_TASK = 'scheduled_fixtures_sync'
const RESULTS_TASK = 'scheduled_results_sync'

// Module level: the batch keeps running while the user leaves /mine/admin,
// so the button state must survive component unmount.
const fullSyncing = ref(false)
const resultsSyncing = ref(false)
const pollPromises = new Map<string, Promise<void>>()

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

type SyncKind = 'full' | 'results'

function syncingRef(kind: SyncKind) {
  return kind === 'full' ? fullSyncing : resultsSyncing
}

export function useAdminSync() {
  const { refresh: refreshFavorites } = useFavoriteFixtures()
  const busy = computed(
    () => fullSyncing.value || resultsSyncing.value,
  )

  async function waitForCompletion(kind: SyncKind) {
    const taskName = kind === 'full' ? FULL_TASK : RESULTS_TASK
    const existing = pollPromises.get(taskName)
    if (existing) return existing
    const flag = syncingRef(kind)
    const pollPromise = (async () => {
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
        const task = data.active_tasks[taskName]
        if (!task || task.status === 'running') continue
        const ok = task.status === 'completed'
        const detail = task.error || `后端返回状态：${task.status}`
        flag.value = false
        if (ok) {
          await refreshFavorites()
          if (kind === 'full') {
            notifySuccess('同步官方 API 数据完成', '赛程、盘口、赛果与自动推荐已更新')
          } else {
            notifySuccess('赛果已更新', '终场比分与训练标签已按日回写')
          }
        } else {
          notifyError(
            kind === 'full' ? '同步官方 API 数据未完成' : '更新赛果未完成',
            detail,
          )
        }
        return
      }
    })().finally(() => {
      pollPromises.delete(taskName)
    })
    pollPromises.set(taskName, pollPromise)
    return pollPromise
  }

  async function hydrateStatus() {
    try {
      const data = await fetchAdminTaskStatus()
      fullSyncing.value =
        data.active_tasks[FULL_TASK]?.status === 'running'
      resultsSyncing.value =
        data.active_tasks[RESULTS_TASK]?.status === 'running'
      if (fullSyncing.value) {
        void waitForCompletion('full').catch(() => {
          fullSyncing.value = false
        })
      }
      if (resultsSyncing.value) {
        void waitForCompletion('results').catch(() => {
          resultsSyncing.value = false
        })
      }
    } catch {
      // Admin page setting load reports authentication/network failures.
    }
  }

  async function runKind(
    kind: SyncKind,
    start: () => Promise<Awaited<ReturnType<typeof triggerScheduledFixturesSync>>>,
    failTitle: string,
    errorTitle: string,
  ) {
    const flag = syncingRef(kind)
    if (flag.value || busy.value) return
    flag.value = true
    const taskName = kind === 'full' ? FULL_TASK : RESULTS_TASK
    try {
      const data = await start()
      const task = data.task_status.active_tasks[taskName]
      if (task?.status === 'running' || data.status === 'accepted') {
        await waitForCompletion(kind)
        return
      }
      const detail =
        task?.error ||
        (task ? `后端返回状态：${task.status}` : '后端未返回任务状态')
      notifyError(failTitle, detail)
    } catch (err) {
      const detail = err instanceof Error ? err.message : '请求失败'
      notifyError(errorTitle, detail)
    } finally {
      if (!pollPromises.has(taskName)) flag.value = false
    }
  }

  async function runSync() {
    await runKind(
      'full',
      triggerScheduledFixturesSync,
      '同步官方 API 数据未完成',
      '同步官方 API 数据失败',
    )
  }

  async function runResultsSync() {
    await runKind(
      'results',
      triggerScheduledResultsSync,
      '更新赛果未完成',
      '更新赛果失败',
    )
  }

  return {
    syncing: readonly(fullSyncing),
    resultsSyncing: readonly(resultsSyncing),
    busy,
    runSync,
    runResultsSync,
    hydrateStatus,
  }
}
