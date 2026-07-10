import { analysisClient, apiClient } from './client'
import type { FixtureResponse, TodayFixturesResponse } from './types'

export async function fetchTodayFixtures(options?: {
  leagueId?: number
  date?: string
  days?: number
}): Promise<TodayFixturesResponse> {
  const { data } = await apiClient.get<TodayFixturesResponse>('/fixtures/today', {
    params: {
      league_id: options?.leagueId,
      date: options?.date,
      days: options?.days,
    },
  })
  return data
}

function isRetryableAnalysisError(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err)
  return /503|500|超时|timeout|ECONNABORTED|网络/i.test(message)
}

/** Detail analysis: auto-retry once on transient server/enrichment failures. */
export async function fetchFixtureAnalysis(fixtureId: number): Promise<FixtureResponse> {
  try {
    const { data } = await analysisClient.get<FixtureResponse>(
      `/fixtures/${fixtureId}/analysis`,
    )
    return data
  } catch (err) {
    if (!isRetryableAnalysisError(err)) throw err
    await new Promise((r) => setTimeout(r, 400))
    const { data } = await analysisClient.get<FixtureResponse>(
      `/fixtures/${fixtureId}/analysis`,
    )
    return data
  }
}
