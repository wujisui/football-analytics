export interface ProbabilitiesResponse {
  /** false = no real probs; do not render fake 33/33/33 */
  available?: boolean
  home_win_prob?: number | null
  draw_prob?: number | null
  away_win_prob?: number | null
}

export interface MatchWinnerOdds {
  bookmaker?: string | null
  home?: string | number | null
  draw?: string | number | null
  away?: string | number | null
  values?: Array<{ label?: string; odd?: string | number | null }>
}

export interface LineOdds {
  bookmaker?: string | null
  bet?: string | null
  line?: string | null
  home?: string | number | null
  away?: string | number | null
  /** Multi-line board; first item is usually the main line. */
  lines?: Array<{
    line?: string | null
    home?: string | number | null
    away?: string | number | null
  }>
  values?: Array<{ label?: string; odd?: string | number | null }>
}

export interface OddsPackage {
  available: boolean
  match_winner?: MatchWinnerOdds | null
  asian_handicap?: LineOdds | null
  goals_ou?: LineOdds | null
  bookmakers?: Array<Record<string, unknown>>
  /** opening = 初盘；current = 即时盘 */
  role?: string | null
  captured_at?: string | null
}

export interface StandingsSnippet {
  available: boolean
  league_id?: number | null
  league_name?: string
  group?: string | null
  home_rank?: number | null
  away_rank?: number | null
  scope?: string
  fetched?: boolean | null
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
  home_id?: number | null
  away_id?: number | null
  score: string
  /** Halftime score e.g. "0-1"; absent on older cached rows. */
  score_ht?: string | null
  league_id?: number | null
  league_name?: string | null
  league_country?: string | null
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
  source?: string | null
}

export interface H2HPackage {
  played: number
  home_wins: number
  draws: number
  away_wins: number
  matches: FormMatch[]
  /** Present after successful H2H summarize; missing means stale/failed row. */
  fetched?: boolean | null
  source?: string | null
}

/** Official API-Sports /predictions; not local ML 「我的预测」. */
export interface BriefingPackage {
  available: boolean
  fetched?: boolean | null
  advice?: string | null
  winner?: {
    id?: number | null
    name?: string | null
    comment?: string | null
  } | null
  win_or_draw?: boolean | null
  under_over?: string | null
  goals?: {
    home?: string | null
    away?: string | null
  } | null
  percent?: {
    home?: string | null
    draw?: string | null
    away?: string | null
  } | null
  comparison?: {
    key: string
    label: string
    home?: string | null
    away?: string | null
  }[]
}

export interface PrematchPackage {
  /** 即时盘 */
  odds: OddsPackage
  /** 初盘（中午定时首次落库后冻结） */
  odds_opening?: OddsPackage | null
  lineups: LineupsPackage
  injuries: InjuriesPackage
  head_to_head: H2HPackage
  home_form: FormPackage
  away_form: FormPackage
  standings?: StandingsSnippet | null
  briefing?: BriefingPackage | null
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
  goal_lean?: string
  both_score_lean?: string
  score_hint?: string
  handicap_lean?: string
  data_source: string
  analyzed_at: string
  cache_status: string
  package?: PrematchPackage | null
}

export interface OpinionFactor {
  id: string
  label: string
  group: string
}

export interface PredictionSnapshot {
  home_win_prob: number
  draw_prob: number
  away_win_prob: number
  recommendation: string
  goal_lean: string
  both_score_lean: string
  score_hint: string
  handicap_lean: string
  factors?: string[]
}

export interface FixtureOddsSnippet {
  available: boolean
  match_winner?: MatchWinnerOdds | null
  asian_handicap?: LineOdds | null
  goals_ou?: LineOdds | null
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
  home_goals?: number | null
  away_goals?: number | null
  league_country?: string | null
  analysis: AnalysisResponse
  home_rank?: number | null
  away_rank?: number | null
  odds_snippet?: FixtureOddsSnippet | null
}

export interface TodayFixturesResponse {
  date: string
  days: number
  total: number
  fixtures: FixtureResponse[]
}

export interface LeagueSummaryResponse {
  league_id: number
  league_name: string
  country: string | null
  today_fixtures_count: number
  upcoming_fixtures_count: number
}

export interface LeaguesListResponse {
  date: string
  days: number
  leagues: LeagueSummaryResponse[]
}
