import { apiClient } from './client'
import type {
  FixtureResponse,
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

export interface FixtureScoreItem {
  fixture_id: number
  status: string
  fixture_date: string
  home_goals?: number | null
  away_goals?: number | null
}

export interface FixtureScoresResponse {
  total: number
  fixtures: FixtureScoreItem[]
}

export async function fetchFixtureScores(
  ids: number[],
): Promise<FixtureScoresResponse> {
  const unique = [...new Set(ids.filter((id) => Number.isFinite(id)))]
  if (!unique.length) return { total: 0, fixtures: [] }
  const { data } = await apiClient.get<FixtureScoresResponse>('/fixtures/scores', {
    params: { ids: unique },
  })
  return data
}

export interface ResultFixture {
  fixture_id: number
  league_id: number
  league_name: string
  league_country?: string | null
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
  handicap_lean?: string | null
  handicap_result?: string | null
  handicap_hit?: boolean | null
  score_hit?: boolean | null
  ou_hit?: boolean | null
  btts_hit?: boolean | null
  result_hit?: boolean | null
  single_result_hit?: boolean | null
}

export interface AccuracyStat {
  hits: number
  total: number
  rate: number | null
}

export interface ResultsAccuracy {
  result: AccuracyStat
  single_result: AccuracyStat
  score: AccuracyStat
  ou: AccuracyStat
  btts: AccuracyStat
  handicap: AccuracyStat
  fixtures_with_prediction: number
  fixtures_finished: number
}

export interface AccuracyDayPoint {
  date: string
  result: AccuracyStat
  score: AccuracyStat
  ou: AccuracyStat
  btts: AccuracyStat
  handicap: AccuracyStat
  fixtures_with_prediction: number
}

export interface ResultsHistoryResponse {
  days: number
  /** true = no lookback cap; all local finished samples */
  all_time?: boolean
  start_date: string
  end_date: string
  overall: ResultsAccuracy
  series: AccuracyDayPoint[]
}

export interface ResultsResponse {
  date: string
  total: number
  fixtures: ResultFixture[]
}

/** Finished/cancelled fixtures for a calendar day or contiguous span (local DB only). */
export async function fetchResults(
  date: string,
  options?: { leagueId?: number; leagueIds?: number[]; days?: number },
): Promise<ResultsResponse> {
  const { data } = await apiClient.get<ResultsResponse>('/fixtures/results', {
    params: {
      date,
      days: options?.days ?? 1,
      league_id: options?.leagueId,
      league_ids: options?.leagueIds,
    },
  })
  return data
}

/** Historical prediction accuracy + daily series for charts. */
export async function fetchResultsHistory(options?: {
  /** 0 / omit = all local finished samples; >0 = last N days */
  days?: number
  /** Series cutoff date YYYY-MM-DD; defaults to today on backend */
  endDate?: string
  leagueId?: number
}): Promise<ResultsHistoryResponse> {
  const { data } = await apiClient.get<ResultsHistoryResponse>('/fixtures/results/history', {
    params: {
      days: options?.days ?? 0,
      end_date: options?.endDate,
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
    const { data } = await apiClient.get<FixtureResponse>(
      `/fixtures/${fixtureId}/analysis`,
    )
    return data
  } catch (err) {
    if (!isRetryableAnalysisError(err)) throw err
    await new Promise((r) => setTimeout(r, 400))
    const { data } = await apiClient.get<FixtureResponse>(
      `/fixtures/${fixtureId}/analysis`,
    )
    return data
  }
}
