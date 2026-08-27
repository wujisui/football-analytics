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
  dense_odds_enabled: boolean
  sync_times: string[]
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

export type OfficialLeagueLookup = {
  league_id: number
  official_name: string
  country: string
  season: string
  league_type: string
  suggested_name: string
  in_catalog: boolean
  from_cache: boolean
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

export type AdminTaskState = {
  status: string
  error?: string
  result?: {
    prematch_odds?: {
      window_start: string | null
      window_days: number
      candidates: number
      attempted: number
      updated: number
      truncated: number
    }
  }
}

export type TriggerTaskResult = {
  status: string
  message: string
  task_status: {
    active_tasks: Record<string, AdminTaskState>
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

const ADMIN_CACHE_PREFIX = 'fa-admin-setting:v2:'
const SUBSCRIPTION_CACHE_KEY = `${ADMIN_CACHE_PREFIX}subscription`
const HOT_LEAGUES_CACHE_KEY = `${ADMIN_CACHE_PREFIX}hot-leagues`
const API_KEY_CACHE_KEY = `${ADMIN_CACHE_PREFIX}api-key`

function readAdminCache<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

function writeAdminCache<T>(key: string, value: T): T {
  try {
    sessionStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Private mode / quota: the API response still remains usable in this render.
  }
  return value
}

export function peekSubscriptionSetting(): SubscriptionSetting | null {
  return readAdminCache<SubscriptionSetting>(SUBSCRIPTION_CACHE_KEY)
}

export function peekHotLeaguesSetting(): HotLeaguesSetting | null {
  return readAdminCache<HotLeaguesSetting>(HOT_LEAGUES_CACHE_KEY)
}

export function peekApiSportsKeySetting(): ApiSportsKeySetting | null {
  return readAdminCache<ApiSportsKeySetting>(API_KEY_CACHE_KEY)
}

export function clearAdminSettingsCache(): void {
  try {
    for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
      const key = sessionStorage.key(index)
      if (key?.startsWith('fa-admin-setting:')) sessionStorage.removeItem(key)
    }
  } catch {
    // Ignore unavailable session storage.
  }
}

/** Admin routes authenticate via the logged-in is_admin session cookie. */
export async function fetchSubscriptionSetting(force = false): Promise<SubscriptionSetting> {
  if (!force) {
    const cached = peekSubscriptionSetting()
    if (cached) return cached
  }
  const { data } = await apiClient.get<SubscriptionSetting>('/admin/settings/subscription')
  return writeAdminCache(SUBSCRIPTION_CACHE_KEY, data)
}

export async function updateSubscriptionSetting(
  subscribed: boolean,
): Promise<SubscriptionSetting> {
  const { data } = await apiClient.patch<SubscriptionSetting>(
    '/admin/settings/subscription',
    { subscribed },
  )
  return writeAdminCache(SUBSCRIPTION_CACHE_KEY, data)
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
  return writeAdminCache(SUBSCRIPTION_CACHE_KEY, data)
}

export async function updateSubscriptionDenseOdds(
  enabled: boolean,
): Promise<SubscriptionSetting> {
  const { data } = await apiClient.patch<SubscriptionSetting>(
    '/admin/settings/subscription-dense-odds',
    {
      enabled,
    },
  )
  return writeAdminCache(SUBSCRIPTION_CACHE_KEY, data)
}

export async function fetchAdminTaskStatus(): Promise<{
  active_tasks: Record<string, AdminTaskState>
}> {
  const { data } = await apiClient.get('/admin/tasks')
  return data
}

export async function fetchHotLeaguesSetting(force = false): Promise<HotLeaguesSetting> {
  if (!force) {
    const cached = peekHotLeaguesSetting()
    if (cached) return cached
  }
  const { data } = await apiClient.get<HotLeaguesSetting>('/admin/settings/hot-leagues')
  return writeAdminCache(HOT_LEAGUES_CACHE_KEY, data)
}

export async function updateHotLeaguesSetting(
  leagueIds: number[],
): Promise<HotLeaguesSetting> {
  const { data } = await apiClient.patch<HotLeaguesSetting>(
    '/admin/settings/hot-leagues',
    { league_ids: leagueIds },
  )
  return writeAdminCache(HOT_LEAGUES_CACHE_KEY, data)
}

export async function createLeagueCategory(name: string): Promise<HotLeaguesSetting> {
  const { data } = await apiClient.post<HotLeaguesSetting>(
    '/admin/settings/league-categories',
    { name },
  )
  return writeAdminCache(HOT_LEAGUES_CACHE_KEY, data)
}

export async function deleteLeagueCategory(
  categoryId: number,
): Promise<HotLeaguesSetting> {
  const { data } = await apiClient.delete<HotLeaguesSetting>(
    `/admin/settings/league-categories/${categoryId}`,
  )
  return writeAdminCache(HOT_LEAGUES_CACHE_KEY, data)
}

export async function lookupOfficialLeague(
  leagueId: number,
): Promise<OfficialLeagueLookup> {
  const { data } = await apiClient.get<OfficialLeagueLookup>(
    `/admin/settings/leagues/${leagueId}/lookup`,
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
  return writeAdminCache(HOT_LEAGUES_CACHE_KEY, data)
}

export async function updateCatalogLeague(
  leagueId: number,
  params: CatalogLeagueUpdate,
): Promise<HotLeaguesSetting> {
  const { data } = await apiClient.patch<HotLeaguesSetting>(
    `/admin/settings/leagues/${leagueId}`,
    params,
  )
  return writeAdminCache(HOT_LEAGUES_CACHE_KEY, data)
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
  const cached = readAdminCache<HotLeaguesSetting>(HOT_LEAGUES_CACHE_KEY)
  if (cached) {
    const leagueId = params.leagueId
    writeAdminCache(HOT_LEAGUES_CACHE_KEY, {
      ...cached,
      league_ids: cached.league_ids.filter((id) => id !== leagueId),
      default_league_ids: cached.default_league_ids.filter((id) => id !== leagueId),
      leagues: cached.leagues.filter((league) => league.league_id !== leagueId),
      categories: cached.categories.map((category) => ({
        ...category,
        leagues: category.leagues.filter((league) => league.league_id !== leagueId),
      })),
    })
  }
  return data
}

export async function fetchApiSportsKeySetting(force = false): Promise<ApiSportsKeySetting> {
  if (!force) {
    const cached = peekApiSportsKeySetting()
    if (cached) return cached
  }
  const { data } = await apiClient.get<ApiSportsKeySetting>('/admin/settings/api-sports-key')
  return writeAdminCache(API_KEY_CACHE_KEY, data)
}

export async function updateApiSportsKeySetting(params: {
  password: string
  keys: string
}): Promise<ApiSportsKeySetting> {
  const { data } = await apiClient.put<ApiSportsKeySetting>(
    '/admin/settings/api-sports-key',
    params,
  )
  return writeAdminCache(API_KEY_CACHE_KEY, data)
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

export async function triggerPrematchOddsSync(
  fixtureIds: number[],
): Promise<TriggerTaskResult> {
  const { data } = await apiClient.post<TriggerTaskResult>(
    '/admin/tasks/trigger',
    { name: 'prematch_odds_sync', fixture_ids: fixtureIds },
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
