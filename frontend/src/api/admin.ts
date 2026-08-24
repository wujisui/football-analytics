import { apiClient } from './client'

export type SubscriptionSetting = {
  subscribed: boolean
  source: 'db' | 'env' | string
  early_odds_enabled: boolean
  sync_times: string[]
  full_sync_completed_today: boolean
  api_remaining: number | null
}

export type HotLeagueItem = {
  league_id: number
  league_name: string
  country: string | null
  selected: boolean
}

export type HotLeaguesSetting = {
  league_ids: number[]
  default_league_ids: number[]
  source: 'db' | 'env' | string
  leagues: HotLeagueItem[]
}

export type ApiSportsKeySetting = {
  key_count: number
  masked_keys: string
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
export async function fetchSubscriptionSetting(): Promise<SubscriptionSetting> {
  const { data } = await apiClient.get<SubscriptionSetting>('/admin/settings/subscription')
  return data
}

export async function updateSubscriptionSetting(
  subscribed: boolean,
): Promise<SubscriptionSetting> {
  const { data } = await apiClient.patch<SubscriptionSetting>(
    '/admin/settings/subscription',
    { subscribed },
  )
  return data
}

export async function updateSubscriptionEarlyOdds(
  enabled: boolean,
): Promise<SubscriptionSetting> {
  const { data } = await apiClient.patch<SubscriptionSetting>(
    '/admin/settings/subscription-early-odds',
    {
      enabled,
    },
  )
  return data
}

export async function fetchAdminTaskStatus(): Promise<{
  active_tasks: Record<string, { status: string; error?: string }>
}> {
  const { data } = await apiClient.get('/admin/tasks')
  return data
}

export async function fetchHotLeaguesSetting(): Promise<HotLeaguesSetting> {
  const { data } = await apiClient.get<HotLeaguesSetting>('/admin/settings/hot-leagues')
  return data
}

export async function updateHotLeaguesSetting(
  leagueIds: number[],
): Promise<HotLeaguesSetting> {
  const { data } = await apiClient.patch<HotLeaguesSetting>(
    '/admin/settings/hot-leagues',
    { league_ids: leagueIds },
  )
  return data
}

export async function fetchApiSportsKeySetting(): Promise<ApiSportsKeySetting> {
  const { data } = await apiClient.get<ApiSportsKeySetting>('/admin/settings/api-sports-key')
  return data
}

export async function updateApiSportsKeySetting(params: {
  password: string
  keys: string
}): Promise<ApiSportsKeySetting> {
  const { data } = await apiClient.put<ApiSportsKeySetting>(
    '/admin/settings/api-sports-key',
    params,
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
