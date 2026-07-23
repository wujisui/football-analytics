import { apiClient } from './client'
import type { FixtureOddsSnippet } from './types'

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
  probabilities_available?: boolean
  home_win_prob?: number
  draw_prob?: number
  away_win_prob?: number
  odds_snippet?: FixtureOddsSnippet | null
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
