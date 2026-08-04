/** 胜 / 平 / 负 — 与详情「统计」近况徽章一致，供 ECharts 等 JS 侧使用。 */
export const WDL_COLORS = {
  win: '#c23b3b',
  draw: '#909399',
  loss: '#3b6fc2',
} as const

export type WdlTone = keyof typeof WDL_COLORS

/**
 * Map recommendation / handicap lean text to WDL tone.
 * Dual picks (胜/平、负/平) take the non-draw side.
 */
export function leanWdlTone(text: string | null | undefined): WdlTone | null {
  const t = (text ?? '').trim()
  if (!t || t.includes('待分析') || t.includes('缺少盘口')) return null
  const hasWin = t.includes('胜')
  const hasDraw = t.includes('平')
  const hasLoss = t.includes('负')
  if (hasWin && !hasLoss) return 'win'
  if (hasLoss && !hasWin) return 'loss'
  if (hasWin && hasLoss) return 'win'
  if (hasDraw) return 'draw'
  return null
}

/** Naive UI `n-tag` outline color aligned with WDL. */
export function wdlTagColor(tone: WdlTone | null):
  | { color: string; textColor: string; borderColor: string }
  | undefined {
  if (!tone) return undefined
  const c = WDL_COLORS[tone]
  return { color: 'transparent', textColor: c, borderColor: c }
}
