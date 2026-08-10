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

function adminHeaders(adminKey: string) {
  return { 'X-Admin-Key': adminKey }
}

export async function fetchScheduledFullDetailSetting(
  adminKey: string,
): Promise<ScheduledFullDetailSetting> {
  const { data } = await apiClient.get<ScheduledFullDetailSetting>(
    '/admin/settings/scheduled-full-detail',
    { headers: adminHeaders(adminKey) },
  )
  return data
}

export async function updateScheduledFullDetailSetting(
  adminKey: string,
  enabled: boolean,
): Promise<ScheduledFullDetailSetting> {
  const { data } = await apiClient.patch<ScheduledFullDetailSetting>(
    '/admin/settings/scheduled-full-detail',
    { enabled },
    { headers: adminHeaders(adminKey) },
  )
  return data
}

export async function triggerScheduledFixturesSync(
  adminKey: string,
): Promise<TriggerTaskResult> {
  const { data } = await apiClient.post<TriggerTaskResult>(
    '/admin/tasks/trigger',
    { name: 'scheduled_fixtures_sync' },
    {
      headers: adminHeaders(adminKey),
      timeout: 5 * 60_000,
    },
  )
  return data
}
