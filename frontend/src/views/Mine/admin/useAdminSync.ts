import { computed, readonly, ref } from 'vue'

import {
  fetchAdminTaskStatus,
  triggerPrematchOddsSync,
  triggerScheduledFixturesSync,
  triggerScheduledResultsSync,
} from '@/api/admin'
import { notifyLocalDataChanged } from '@/composables/useClientDataRevision'
import { notifyError, notifySuccess } from '@/utils/globalNotify'

const FULL_TASK = 'scheduled_fixtures_sync'
const RESULTS_TASK = 'scheduled_results_sync'
const PREMATCH_ODDS_TASK = 'prematch_odds_sync'

// Module level: the batch keeps running while the user leaves /mine/admin,
// so the button state must survive component unmount.
const fullSyncing = ref(false)
const resultsSyncing = ref(false)
const prematchOddsSyncing = ref(false)
const officialSyncing = ref(false)
const pollPromises = new Map<string, Promise<void>>()
let officialIdlePromise: Promise<void> | null = null
let statusHydrated = false

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

type SyncKind = 'full' | 'results' | 'prematchOdds'

function syncingRef(kind: SyncKind) {
  if (kind === 'full') return fullSyncing
  if (kind === 'results') return resultsSyncing
  return prematchOddsSyncing
}

function taskNameFor(kind: SyncKind) {
  if (kind === 'full') return FULL_TASK
  if (kind === 'results') return RESULTS_TASK
  return PREMATCH_ODDS_TASK
}

export function useAdminSync() {
  const busy = computed(
    () =>
      fullSyncing.value ||
      resultsSyncing.value ||
      prematchOddsSyncing.value ||
      officialSyncing.value,
  )

  function syncOfficialBusy(
    data: Awaited<ReturnType<typeof fetchAdminTaskStatus>>,
  ) {
    officialSyncing.value = Boolean(data.official_sync_busy)
  }

  function waitForOfficialIdle() {
    if (officialIdlePromise) return officialIdlePromise
    officialIdlePromise = (async () => {
      while (officialSyncing.value) {
        await delay(1500)
        try {
          const data = await fetchAdminTaskStatus()
          syncOfficialBusy(data)
        } catch {
          // Keep the current busy state; a later status read can recover.
        }
      }
    })().finally(() => {
      officialIdlePromise = null
    })
    return officialIdlePromise
  }

  async function waitForCompletion(kind: SyncKind) {
    const taskName = taskNameFor(kind)
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
          syncOfficialBusy(data)
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
          await notifyLocalDataChanged()
          if (kind === 'full') {
            notifySuccess('同步官方 API 数据完成', '赛程、盘口、赛果与自动推荐已更新')
          } else if (kind === 'results') {
            notifySuccess('赛果已更新', '终场比分与训练标签已按日回写')
          } else {
            const stats = task.result?.prematch_odds
            notifySuccess(
              '批量更新盘口完成',
              stats
                ? `名单 ${stats.candidates} 场，尝试 ${stats.attempted} 场，成功更新 ${stats.updated} 场`
                : '已完成当前【比赛】筛选场次的盘口更新',
            )
          }
        } else {
          notifyError(
            kind === 'full'
              ? '同步官方 API 数据未完成'
              : kind === 'results'
                ? '更新赛果未完成'
                : '批量更新盘口未完成',
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

  async function hydrateStatus(force = false) {
    if (statusHydrated && !force) return
    try {
      const data = await fetchAdminTaskStatus()
      statusHydrated = true
      syncOfficialBusy(data)
      fullSyncing.value =
        data.active_tasks[FULL_TASK]?.status === 'running'
      resultsSyncing.value =
        data.active_tasks[RESULTS_TASK]?.status === 'running'
      prematchOddsSyncing.value =
        data.active_tasks[PREMATCH_ODDS_TASK]?.status === 'running'
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
      if (prematchOddsSyncing.value) {
        void waitForCompletion('prematchOdds').catch(() => {
          prematchOddsSyncing.value = false
        })
      }
      if (
        officialSyncing.value
        && !fullSyncing.value
        && !resultsSyncing.value
        && !prematchOddsSyncing.value
      ) {
        void waitForOfficialIdle()
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
    const taskName = taskNameFor(kind)
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

  async function runPrematchOddsSync(fixtureIds: number[]) {
    await runKind(
      'prematchOdds',
      () => triggerPrematchOddsSync(fixtureIds),
      '批量更新盘口未完成',
      '批量更新盘口失败',
    )
  }

  return {
    syncing: readonly(fullSyncing),
    resultsSyncing: readonly(resultsSyncing),
    prematchOddsSyncing: readonly(prematchOddsSyncing),
    officialSyncing: readonly(officialSyncing),
    busy,
    runSync,
    runResultsSync,
    runPrematchOddsSync,
    hydrateStatus,
  }
}
