export interface RegulationScore {
  home_goals?: number | null
  away_goals?: number | null
}

export interface ExtraScore extends RegulationScore {
  et_home_goals?: number | null
  et_away_goals?: number | null
  pen_home?: number | null
  pen_away?: number | null
}

/** Minimal shape for ResultHitTags (results list + finished favorites). */
export interface HitTagFixture {
  has_prediction?: boolean
  result_hit?: boolean | null
  score_hit?: boolean | null
  ou_hit?: boolean | null
  btts_hit?: boolean | null
  handicap_result?: string | null
  handicap_hit?: boolean | null
}

export function hitTagType(
  hit: boolean | null | undefined,
): 'success' | 'error' | 'default' {
  if (hit === true) return 'success'
  if (hit === false) return 'error'
  return 'default'
}

/** Main board = regulation 90'. */
export function resultScoreText(fx: RegulationScore): string {
  if (fx.home_goals == null || fx.away_goals == null) return '—'
  return `${fx.home_goals} : ${fx.away_goals}`
}

function etScoreText(fx: ExtraScore): string | null {
  if (fx.et_home_goals == null || fx.et_away_goals == null) return null
  return `${fx.et_home_goals}-${fx.et_away_goals}`
}

function penScoreText(fx: ExtraScore): string | null {
  if (fx.pen_home == null || fx.pen_away == null) return null
  return `${fx.pen_home}-${fx.pen_away}`
}

/** One line under main score: 加时：a-b；点球：c-d */
export function resultExtraScoreLine(fx: ExtraScore): string | null {
  const parts: string[] = []
  const et = etScoreText(fx)
  const pen = penScoreText(fx)
  if (et) parts.push(`加时：${et}`)
  if (pen) parts.push(`点球：${pen}`)
  return parts.length ? parts.join('；') : null
}
