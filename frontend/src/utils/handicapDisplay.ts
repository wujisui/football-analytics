export const HANDICAP_MISSING_LABEL = '缺少盘口数据分析'

/** 有符号让球线文案：主让为负、客让为正、平手为 0。 */
export function formatSignedHandicapLine(line: number): string {
  if (!Number.isFinite(line)) return ''
  if (Math.abs(line) < 1e-9) return '0'
  return line > 0 ? `+${line}` : String(line)
}

export function isPredictionPending(text: string | null | undefined): boolean {
  const value = (text ?? '').trim()
  return !value || value.includes('缺少盘口') || value.includes('待分析')
}

/**
 * Short pick for compact hit tags: 让负(-1) → 让负.
 * Also strips brief 主让/客让/平手 suffixes if any remain.
 */
export function handicapLeanLabel(text: string | null | undefined): string {
  const value = (text ?? '').trim()
  if (!value) return ''
  return value
    .replace(/\s*[（(]\s*(?:主让|客让)\s*\d+(?:\.\d+)?\s*[）)]\s*$/, '')
    .replace(/\s*[（(]\s*平手\s*[）)]\s*$/, '')
    .replace(/\s*[（(]\s*[+-]?\d+(?:\.\d+)?\s*[）)]\s*$/, '')
}

/**
 * Render a frozen lean as an Asian-bettable side: a standalone 让平 becomes
 * non-bettable 走水, and 让平 is dropped from dual picks.
 */
export function adaptHandicapLean(text: string | null | undefined): string {
  const value = (text ?? '').trim()
  if (!value) return value
  if (!value.includes('平')) return value
  if (/^让平(?:\s*[（(]|$)/.test(value)) {
    return value.replace('让平', '走水')
  }
  const stripped = value.replace(/\/平|平\//g, '')
  return stripped.trim() || value
}
