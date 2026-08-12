import { apiClient } from './client'
import type { FixtureOddsSnippet } from './types'

/** Market key written by backend auto-favorites ranking. */
export type AutoFavoriteMarket = '1x2' | 'ah' | 'ou' | 'btts' | 'score'

export interface FavoriteFixtureRecord {
  fixture_id: number
  home_team_name: string
  away_team_name: string
  league_id: number
  league_name: string
  league_country?: string | null
  fixture_date: string
  status?: string
  home_goals?: number | null
  away_goals?: number | null
  saved_at: string
  has_prediction?: boolean
  recommendation?: string
  handicap_lean?: string
  score_hint?: string
  goal_lean?: string
  both_score_lean?: string
  /** Finished settlement (same as results list); omitted while not evaluable. */
  handicap_result?: string | null
  handicap_hit?: boolean | null
  score_hit?: boolean | null
  ou_hit?: boolean | null
  btts_hit?: boolean | null
  result_hit?: boolean | null
  single_result_hit?: boolean | null
  probabilities_available?: boolean
  home_win_prob?: number
  draw_prob?: number
  away_win_prob?: number
  odds_snippet?: FixtureOddsSnippet | null
  home_rank?: number | null
  away_rank?: number | null
  /** auto = scheduled algorithm pick; manual = user star. */
  source?: 'manual' | 'auto' | string
  auto_market?: AutoFavoriteMarket | string | null
  auto_lean?: string | null
}

export interface FavoriteFixturesResponse {
  total: number
  favorites: FavoriteFixtureRecord[]
}

export async function fetchFavorites(): Promise<FavoriteFixturesResponse> {
  const { data } = await apiClient.get<FavoriteFixturesResponse>('/favorites')
  return data
}

export async function addFavorite(fixtureId: number): Promise<FavoriteFixtureRecord> {
  const { data } = await apiClient.post<FavoriteFixtureRecord>('/favorites', {
    fixture_id: fixtureId,
  })
  return data
}

export async function deleteFavorite(fixtureId: number): Promise<void> {
  await apiClient.delete(`/favorites/${fixtureId}`)
}
