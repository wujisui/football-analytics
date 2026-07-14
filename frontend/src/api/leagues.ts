import { apiClient } from './client'

export interface LeagueCatalogItem {
  league_id: number
  league_name: string
  country: string | null
  season?: string | null
}

export interface LeagueFilterOption {
  league_id: number
  league_name: string
  country: string | null
  fixtures_count: number
  tier: 'configured' | 'extra'
  default_checked: boolean
  locally_loaded: boolean
}

export interface LeagueFilterOptionsResponse {
  date: string
  configured: LeagueFilterOption[]
  extra: LeagueFilterOption[]
  /** Full leagues.json list (for force-refresh fallback). */
  catalog: LeagueCatalogItem[]
  discovery_source: string
  message?: string | null
}

/** Today-matched filter options (+ embedded configured catalog). */
export async function fetchLeagueFilterOptions(params?: {
  date?: string
  discover?: boolean
}): Promise<LeagueFilterOptionsResponse> {
  const { data } = await apiClient.get<LeagueFilterOptionsResponse>(
    '/leagues/filter-options',
    {
      params: {
        date: params?.date,
        discover: params?.discover,
      },
    },
  )
  return data
}
