import type { ResultFixture } from '@/api/fixtures'

export function hitTagType(
  hit: boolean | null | undefined,
): 'success' | 'error' | 'default' {
  if (hit === true) return 'success'
  if (hit === false) return 'error'
  return 'default'
}

export function hitLabel(hit: boolean | null | undefined): string {
  if (hit === true) return '中'
  if (hit === false) return '未中'
  return '—'
}

/** Main board = regulation 90'. */
export function resultScoreText(fx: ResultFixture): string {
  if (fx.home_goals == null || fx.away_goals == null) return '—'
  return `${fx.home_goals} : ${fx.away_goals}`
}

function etScoreText(fx: ResultFixture): string | null {
  if (fx.et_home_goals == null || fx.et_away_goals == null) return null
  return `${fx.et_home_goals}-${fx.et_away_goals}`
}

function penScoreText(fx: ResultFixture): string | null {
  if (fx.pen_home == null || fx.pen_away == null) return null
  return `${fx.pen_home}-${fx.pen_away}`
}

/** One line under main score: 加时：a-b；点球：c-d */
export function resultExtraScoreLine(fx: ResultFixture): string | null {
  const parts: string[] = []
  const et = etScoreText(fx)
  const pen = penScoreText(fx)
  if (et) parts.push(`加时：${et}`)
  if (pen) parts.push(`点球：${pen}`)
  return parts.length ? parts.join('；') : null
}
