import { computed, readonly, ref } from 'vue'

import { triggerScheduledFixturesSync } from '@/api/admin'
import { useFavoriteFixtures } from '@/composables/useFavoriteFixtures'
import { notifyError, notifySuccess } from '@/utils/globalNotify'

type SyncOutcome = { ok: boolean; at: number; detail: string }

// Module level: the batch keeps running while the user leaves /mine/admin,
// so the button state must survive component unmount.
const syncing = ref(false)
const lastOutcome = ref<SyncOutcome | null>(null)

function formatTime(at: number) {
  return new Date(at).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function useAdminSync() {
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
      // 只有 completed 才是真同步；skipped（未配置 Key）也必须报出来，
      // 否则批次一次官方请求都没发也会提示「同步完成」。
      if (task?.status !== 'completed') {
        const detail =
          task?.error ||
          (task ? `后端返回状态：${task.status}` : '后端未返回任务状态')
        lastOutcome.value = { ok: false, at: Date.now(), detail }
        notifyError('同步官方 API 数据未完成', detail)
        return
      }
      lastOutcome.value = { ok: true, at: Date.now(), detail: '' }
      await refreshFavorites()
      notifySuccess('同步官方 API 数据完成', '赛程、盘口、赛果与自动推荐已更新')
    } catch (err) {
      const detail = err instanceof Error ? err.message : '请求失败'
      lastOutcome.value = { ok: false, at: Date.now(), detail }
      notifyError('同步官方 API 数据失败', detail)
    } finally {
      syncing.value = false
    }
  }

  return {
    syncing: readonly(syncing),
    statusText,
    runSync,
  }
}
