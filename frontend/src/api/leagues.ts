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
}

export interface LeagueCatalogResponse {
  leagues: LeagueCatalogItem[]
}

/** Primary leagues from config/leagues.json (热门 / 一级目录). */
export async function fetchLeagueCatalog(): Promise<LeagueCatalogResponse> {
  const { data } = await apiClient.get<LeagueCatalogResponse>('/leagues/catalog')
  return data
}

/** Locally stored, odds-backed filter options for the selected day. */
export async function fetchLeagueFilterOptions(params?: {
  date?: string
}): Promise<LeagueFilterOptionsResponse> {
  const { data } = await apiClient.get<LeagueFilterOptionsResponse>(
    '/leagues/filter-options',
    {
      params: {
        date: params?.date,
      },
    },
  )
  return data
}
