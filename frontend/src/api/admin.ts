import { apiClient } from './client'

export type ScheduledFullDetailSetting = {
  enabled: boolean
  source: 'db' | 'env' | string
  budget: number
}

export type FreeQuotaSetting = {
  enabled: boolean
  source: 'db' | 'env' | string
  sync_hours: number[]
  catch_up_started?: boolean
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

export type ResetMatchHistoryReport = {
  apply: boolean
  fixtures: number
  pre_match_data: number
  match_features: number
  auto_pick_snapshots: number
  favorite_fixtures: number
  league_standings: number
  api_snapshots: number
  incentive_settings_cleared: number
  model_files_removed: number
  cache_cleared: boolean
  kept: string[]
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

export async function fetchFreeQuotaSetting(): Promise<FreeQuotaSetting> {
  const { data } = await apiClient.get<FreeQuotaSetting>('/admin/settings/free-quota')
  return data
}

export async function updateFreeQuotaSetting(enabled: boolean): Promise<FreeQuotaSetting> {
  const { data } = await apiClient.patch<FreeQuotaSetting>('/admin/settings/free-quota', {
    enabled,
  })
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

export async function previewResetMatchHistory(): Promise<ResetMatchHistoryReport> {
  const { data } = await apiClient.get<ResetMatchHistoryReport>('/admin/reset-match-history')
  return data
}

export async function resetMatchHistory(params: {
  password: string
  apply: boolean
}): Promise<ResetMatchHistoryReport> {
  const { data } = await apiClient.post<ResetMatchHistoryReport>(
    '/admin/reset-match-history',
    params,
    { timeout: 5 * 60_000 },
  )
  return data
}
