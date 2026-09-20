/** 胜 / 平 / 负 — 与详情「统计」近况徽章一致，供 ECharts 等 JS 侧使用。 */
export const WDL_COLORS = {
  win: '#c23b3b',
  draw: '#909399',
  loss: '#3b6fc2',
} as const

export type WdlTone = keyof typeof WDL_COLORS

/**
 * Map recommendation / handicap lean text to WDL tone.
 * Dual picks (主胜/和局、客胜/和局) take the non-draw side.
 */
export function leanWdlTone(text: string | null | undefined): WdlTone | null {
  const t = (text ?? '').trim()
  if (!t || t.includes('待分析') || t.includes('缺少盘口')) return null
  if (
    t.includes('客胜') ||
    t.startsWith('客') ||
    t.includes('让负') ||
    t === '负' ||
    t.startsWith('负/')
  ) {
    return 'loss'
  }
  if (
    t.includes('主胜') ||
    t.startsWith('主') ||
    t.includes('让胜') ||
    t === '胜' ||
    t.startsWith('胜/')
  ) {
    return 'win'
  }
  if (t.includes('和局') || t.includes('平')) return 'draw'
  return null
}

/** Borderless WDL tag with a soft business-color background. */
export function wdlTagColor(tone: WdlTone | null):
  | { color: string; textColor: string; borderColor: string }
  | undefined {
  if (!tone) return undefined
  const c = WDL_COLORS[tone]
  return {
    color: `${c}29`,
    textColor: c,
    borderColor: 'transparent',
  }
}
