export interface ProbabilitiesResponse {
  home_win_prob: number
  draw_prob: number
  away_win_prob: number
}

export interface AnalysisResponse {
  fixture_id: number
  home_team_name: string
  away_team_name: string
  league_name: string
  fixture_date: string
  status: string
  probabilities: ProbabilitiesResponse
  confidence: string
  recommendation: string
  data_source: string
  analyzed_at: string
  cache_status: string
}

export interface FixtureResponse {
  fixture_id: number
  league_id: number
  league_name: string
  home_team_id: number
  away_team_id: number
  home_team_name: string
  away_team_name: string
  fixture_date: string
  status: string
  analysis: AnalysisResponse
}

export interface TodayFixturesResponse {
  date: string
  total: number
  fixtures: FixtureResponse[]
}

export interface LeagueSummaryResponse {
  league_id: number
  league_name: string
  country: string | null
  today_fixtures_count: number
}

export interface LeaguesListResponse {
  leagues: LeagueSummaryResponse[]
}
