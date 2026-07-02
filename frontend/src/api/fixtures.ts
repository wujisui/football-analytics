import { apiClient } from './client'
import type { FixtureResponse, TodayFixturesResponse } from './types'

export async function fetchTodayFixtures(leagueId?: number): Promise<TodayFixturesResponse> {
  const { data } = await apiClient.get<TodayFixturesResponse>('/fixtures/today', {
    params: leagueId !== undefined ? { league_id: leagueId } : undefined,
  })
  return data
}

export async function fetchFixtureAnalysis(fixtureId: number): Promise<FixtureResponse> {
  const { data } = await apiClient.get<FixtureResponse>(`/fixtures/${fixtureId}/analysis`)
  return data
}
