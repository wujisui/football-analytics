import { apiClient } from './client'

export type ScheduledFullDetailSetting = {
  enabled: boolean
  source: 'db' | 'env' | string
}

export type TriggerTaskResult = {
  status: string
  message: string
  task_status: {
    active_tasks: Record<
      string,
      {
        status: string
        error?: string
      }
    >
  }
}

/** Admin routes authenticate via the logged-in is_admin session cookie. */
export async function fetchScheduledFullDetailSetting(): Promise<ScheduledFullDetailSetting> {
  const { data } = await apiClient.get<ScheduledFullDetailSetting>(
    '/admin/settings/scheduled-full-detail',
  )
  return data
}

export async function updateScheduledFullDetailSetting(
  enabled: boolean,
): Promise<ScheduledFullDetailSetting> {
  const { data } = await apiClient.patch<ScheduledFullDetailSetting>(
    '/admin/settings/scheduled-full-detail',
    { enabled },
  )
  return data
}

export async function triggerScheduledFixturesSync(): Promise<TriggerTaskResult> {
  const { data } = await apiClient.post<TriggerTaskResult>(
    '/admin/tasks/trigger',
    { name: 'scheduled_fixtures_sync' },
    { timeout: 5 * 60_000 },
  )
  return data
}
