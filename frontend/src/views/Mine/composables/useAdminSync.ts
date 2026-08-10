import { computed, readonly, ref } from 'vue'

import { triggerScheduledFixturesSync } from '@/api/admin'
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
  const statusText = computed(() => {
    if (syncing.value) return '同步进行中，完成后会全局提示'
    const outcome = lastOutcome.value
    if (!outcome) return ''
    return outcome.ok
      ? `上次同步成功：${formatTime(outcome.at)}`
      : `上次同步失败（${formatTime(outcome.at)}）：${outcome.detail}`
  })

  async function runSync(adminKey: string) {
    if (syncing.value || !adminKey) return
    syncing.value = true
    try {
      const data = await triggerScheduledFixturesSync(adminKey)
      const task = data.task_status.active_tasks.scheduled_fixtures_sync
      if (task?.status === 'failed') {
        const detail = task.error || '后端未返回失败原因'
        lastOutcome.value = { ok: false, at: Date.now(), detail }
        notifyError('同步官方 API 数据失败', detail)
        return
      }
      lastOutcome.value = { ok: true, at: Date.now(), detail: '' }
      notifySuccess('同步官方 API 数据完成', '赛程、盘口与赛果已更新，刷新列表即可看到')
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
