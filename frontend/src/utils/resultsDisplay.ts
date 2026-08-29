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
  /** Frozen handicap prediction copy (handicap tag label). */
  handicap_lean?: string | null
  result_hit?: boolean | null
  /** Daily auto-pick settlement (catalog tips). */
  auto_pick_hit?: boolean | null
  auto_pick_lean?: string | null
  /** Which play carried the daily pick; marks that tag with [荐]. */
  auto_pick_market?: string | null
  /** 0.5–5 star quality when this fixture was a daily pick. */
  quality_rating?: number | null
  score_hit?: boolean | null
  ou_hit?: boolean | null
  btts_hit?: boolean | null
  /** Present when handicap was evaluable. */
  handicap_result?: string | null
  handicap_hit?: boolean | null
}

export function hitTagType(
  hit: boolean | null | undefined,
): 'error' | 'default' {
  return hit === true ? 'error' : 'default'
}

/** 已结算且未命中：标签降级为不可点的作废态（样式类 fa-tag-missed）。 */
export function hitTagMissed(hit: boolean | null | undefined): boolean {
  return hit === false
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
