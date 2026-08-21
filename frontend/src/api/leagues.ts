import { apiClient } from './client'

export interface LeagueFilterOption {
  league_id: number
  league_name: string
  country: string | null
  fixtures_count: number
  tier: 'configured' | 'extra'
  default_checked: boolean
}

export interface LeagueFilterOptionsResponse {
  date: string
  configured: LeagueFilterOption[]
  extra: LeagueFilterOption[]
}

export interface LeagueCatalogItem {
  league_id: number
  league_name: string
  country: string | null
  season: string | null
  hot: boolean
}

export interface LeagueCatalogResponse {
  leagues: LeagueCatalogItem[]
}

/** Catalog from config/leagues.json, with admin 热门 flags. */
export async function fetchLeagueCatalog(): Promise<LeagueCatalogResponse> {
  const { data } = await apiClient.get<LeagueCatalogResponse>('/leagues/catalog')
  return data
}

/** Locally stored filter options for the selected day (counts only). */
export async function fetchLeagueFilterOptions(params?: {
  date?: string
  days?: number
  /** prematch = pending (未开赛); results = finished/live day checklist */
  scope?: 'prematch' | 'results'
}): Promise<LeagueFilterOptionsResponse> {
  const { data } = await apiClient.get<LeagueFilterOptionsResponse>(
    '/leagues/filter-options',
    {
      params: {
        date: params?.date,
        days: params?.days,
        scope: params?.scope,
      },
    },
  )
  return data
}
