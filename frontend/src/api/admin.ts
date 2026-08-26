import { apiClient } from './client'

export type LastSyncRun = {
  finished_at: string
  status: 'completed' | 'failed' | string
  label: string
  quota_used: number
  api_remaining: number | null
  error: string | null
}

export type SubscriptionSetting = {
  subscribed: boolean
  source: 'db' | 'env' | string
  early_odds_enabled: boolean
  sync_times: string[]
  full_sync_completed_today: boolean
  api_remaining: number | null
  last_sync: LastSyncRun | null
}

export type HotLeagueItem = {
  league_id: number
  league_name: string
  country: string | null
  category_id: number
  selected: boolean
  protected: boolean
}

export type HotLeagueCategory = {
  category_id: number
  category_name: string
  leagues: HotLeagueItem[]
}

export type HotLeaguesSetting = {
  league_ids: number[]
  default_league_ids: number[]
  source: 'db'
  leagues: HotLeagueItem[]
  categories: HotLeagueCategory[]
}

export type CatalogLeagueCreate = {
  league_id: number
  league_name: string
  country: string
  category_id: number
  selected: boolean
}

export type CatalogLeagueUpdate = {
  league_id?: number
  league_name?: string
  country?: string
  category_id?: number
}

export type CatalogLeagueDeleteReport = {
  apply: boolean
  league_id: number
  league_name: string
  fixtures: number
  pre_match_data: number
  match_features: number
  auto_pick_snapshots: number
  favorite_fixtures: number
  league_standings: number
  api_snapshots: number
  orphan_teams: number
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

export async function createLeagueCategory(name: string): Promise<HotLeaguesSetting> {
  const { data } = await apiClient.post<HotLeaguesSetting>(
    '/admin/settings/league-categories',
    { name },
  )
  return data
}

export async function deleteLeagueCategory(
  categoryId: number,
): Promise<HotLeaguesSetting> {
  const { data } = await apiClient.delete<HotLeaguesSetting>(
    `/admin/settings/league-categories/${categoryId}`,
  )
  return data
}

export async function createCatalogLeague(
  params: CatalogLeagueCreate,
): Promise<HotLeaguesSetting> {
  const { data } = await apiClient.post<HotLeaguesSetting>(
    '/admin/settings/leagues',
    params,
  )
  return data
}

export async function updateCatalogLeague(
  leagueId: number,
  params: CatalogLeagueUpdate,
): Promise<HotLeaguesSetting> {
  const { data } = await apiClient.patch<HotLeaguesSetting>(
    `/admin/settings/leagues/${leagueId}`,
    params,
  )
  return data
}

export async function updateCatalogLeagueCategory(
  leagueId: number,
  categoryId: number,
): Promise<HotLeaguesSetting> {
  return updateCatalogLeague(leagueId, { category_id: categoryId })
}

export async function previewCatalogLeagueDelete(
  leagueId: number,
): Promise<CatalogLeagueDeleteReport> {
  const { data } = await apiClient.get<CatalogLeagueDeleteReport>(
    `/admin/settings/leagues/${leagueId}/delete-preview`,
    { timeout: 5 * 60_000 },
  )
  return data
}

export async function deleteCatalogLeague(params: {
  leagueId: number
  password: string
  apply: true
}): Promise<CatalogLeagueDeleteReport> {
  const { data } = await apiClient.post<CatalogLeagueDeleteReport>(
    `/admin/settings/leagues/${params.leagueId}/delete`,
    { password: params.password, apply: true },
    { timeout: 5 * 60_000 },
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

export async function triggerScheduledResultsSync(): Promise<TriggerTaskResult> {
  const { data } = await apiClient.post<TriggerTaskResult>(
    '/admin/tasks/trigger',
    { name: 'scheduled_results_sync' },
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
