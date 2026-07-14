import { analysisClient, apiClient } from './client'
import type {
  FixtureResponse,
  OpinionFactor,
  PredictionSnapshot,
  TodayFixturesResponse,
} from './types'

export async function fetchTodayFixtures(options?: {
  leagueIds?: number[]
  date?: string
  days?: number
}): Promise<TodayFixturesResponse> {
  const { data } = await apiClient.get<TodayFixturesResponse>('/fixtures/today', {
    params: {
      league_ids: options?.leagueIds,
      date: options?.date,
      days: options?.days,
    },
  })
  return data
}

export interface SyncFixturesResult {
  status: string
  fixtures_saved: number
  days: number
  date?: string | null
  message: string
  retry_after_seconds?: number | null
}

/** Force re-fetch from official API into local DB (bypasses day cache). */
export async function syncFixtures(options?: {
  days?: number
  date?: string
  includeResults?: boolean
  leagueIds?: number[]
}): Promise<SyncFixturesResult> {
  const { data } = await apiClient.post<SyncFixturesResult>('/fixtures/sync', null, {
    params: {
      days: options?.days,
      date: options?.date,
      include_results: options?.includeResults ?? true,
      league_ids: options?.leagueIds,
    },
    // Fixtures return first; odds/results continue in a server background task.
    timeout: 90_000,
  })
  return data
}

export interface ResultFixture {
  fixture_id: number
  league_id: number
  league_name: string
  home_team_id: number
  away_team_id: number
  home_team_name: string
  away_team_name: string
  fixture_date: string
  status: string
  /** Official short: FT / AET / PEN */
  status_short?: string | null
  /** Regulation (90') */
  home_goals?: number | null
  away_goals?: number | null
  /** Extra time board (usually cumulative after ET) */
  et_home_goals?: number | null
  et_away_goals?: number | null
  pen_home?: number | null
  pen_away?: number | null
  has_prediction?: boolean
  recommendation?: string | null
  score_hint?: string | null
  goal_lean?: string | null
  both_score_lean?: string | null
  score_hit?: boolean | null
  ou_hit?: boolean | null
  btts_hit?: boolean | null
  result_hit?: boolean | null
}

export interface AccuracyStat {
  hits: number
  total: number
  rate: number | null
}

export interface ResultsAccuracy {
  result: AccuracyStat
  score: AccuracyStat
  ou: AccuracyStat
  btts: AccuracyStat
  fixtures_with_prediction: number
  fixtures_finished: number
}

export interface AccuracyDayPoint {
  date: string
  result_rate: number | null
  score_rate: number | null
  ou_rate: number | null
  btts_rate: number | null
  result: AccuracyStat
  score: AccuracyStat
  ou: AccuracyStat
  btts: AccuracyStat
  fixtures_with_prediction: number
  fixtures_finished: number
}

export interface ResultsHistoryResponse {
  days: number
  start_date: string
  end_date: string
  overall: ResultsAccuracy
  series: AccuracyDayPoint[]
}

export interface ResultsResponse {
  date: string
  total: number
  fixtures: ResultFixture[]
  accuracy?: ResultsAccuracy
}

/** Finished/cancelled fixtures for a calendar day (local DB only). */
export async function fetchResults(date: string, leagueId?: number): Promise<ResultsResponse> {
  const { data } = await apiClient.get<ResultsResponse>('/fixtures/results', {
    params: {
      date,
      league_id: leagueId,
    },
  })
  return data
}

/** Historical prediction accuracy + daily series for charts. */
export async function fetchResultsHistory(options?: {
  days?: number
  leagueId?: number
}): Promise<ResultsHistoryResponse> {
  const { data } = await apiClient.get<ResultsHistoryResponse>('/fixtures/results/history', {
    params: {
      days: options?.days ?? 30,
      league_id: options?.leagueId,
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

export async function fetchOpinionFactors(): Promise<OpinionFactor[]> {
  const { data } = await apiClient.get<{ factors: OpinionFactor[] }>(
    '/fixtures/opinion-factors',
  )
  return data.factors
}

export async function adjustFixturePrediction(
  fixtureId: number,
  factors: string[],
): Promise<PredictionSnapshot> {
  const { data } = await apiClient.post<PredictionSnapshot>(
    `/fixtures/${fixtureId}/adjust`,
    { factors },
  )
  return data
}
