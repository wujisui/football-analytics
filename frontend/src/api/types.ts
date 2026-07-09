export interface ProbabilitiesResponse {
  home_win_prob: number
  draw_prob: number
  away_win_prob: number
}

export interface MatchWinnerOdds {
  bookmaker?: string | null
  home?: string | number | null
  draw?: string | number | null
  away?: string | number | null
  values?: Array<{ label?: string; odd?: string | number | null }>
}

export interface OddsPackage {
  available: boolean
  match_winner?: MatchWinnerOdds | null
  bookmakers?: Array<Record<string, unknown>>
}

export interface LineupPlayer {
  id?: number | null
  name: string
  number?: number | string | null
  pos?: string | null
  grid?: string | null
}

export interface TeamLineup {
  team_id?: number | null
  team_name: string
  formation?: string | null
  coach?: string | null
  start_xi: LineupPlayer[]
  substitutes: LineupPlayer[]
}

export interface LineupsPackage {
  available: boolean
  home?: TeamLineup | null
  away?: TeamLineup | null
}

export interface InjuryItem {
  player_id?: number | null
  player_name: string
  type?: string | null
  reason?: string | null
}

export interface InjuriesPackage {
  available: boolean
  home: InjuryItem[]
  away: InjuryItem[]
}

export interface FormMatch {
  fixture_id?: number | null
  date?: string | null
  home: string
  away: string
  score: string
  result?: string | null
  outcome_for_current_home?: string | null
}

export interface FormPackage {
  team_id?: number | null
  played: number
  wins: number
  draws: number
  losses: number
  form?: string
  matches: FormMatch[]
}

export interface H2HPackage {
  played: number
  home_wins: number
  draws: number
  away_wins: number
  matches: FormMatch[]
}

export interface PrematchPackage {
  odds: OddsPackage
  lineups: LineupsPackage
  injuries: InjuriesPackage
  head_to_head: H2HPackage
  home_form: FormPackage
  away_form: FormPackage
  home_formation?: string | null
  away_formation?: string | null
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
  package?: PrematchPackage | null
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
