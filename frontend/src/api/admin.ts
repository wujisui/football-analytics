import { apiClient } from './client'

export type ScheduledFullDetailSetting = {
  enabled: boolean
  source: 'db' | 'env' | string
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
