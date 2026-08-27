import {
  formatSignedHandicapLine,
  jcHandicapLine,
  type HandicapRuleset,
} from '@/utils/handicapRuleset'

export const HANDICAP_MISSING_LABEL = '缺少盘口数据分析'

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

const LEAN_LINE_RE = /[（(]\s*([+-]?\d+(?:\.\d+)?)\s*[）)]\s*$/

/**
 * Remap a frozen lean for the reader's ruleset: Asian renders a standalone
 * 让平 as non-bettable 走水 and drops 让平 from dual picks; 竞彩 shows the
 * whole-goal line it settles on（让胜(-0.5) → 让胜(-1)）。
 */
export function adaptHandicapLean(
  text: string | null | undefined,
  ruleset: HandicapRuleset = 'asian',
): string {
  const value = (text ?? '').trim()
  if (!value) return value
  if (ruleset === 'jc') {
    const matched = value.match(LEAN_LINE_RE)
    if (!matched) return value
    const rounded = jcHandicapLine(Number(matched[1]))
    return value.replace(LEAN_LINE_RE, `(${formatSignedHandicapLine(rounded)})`)
  }
  if (!value.includes('平')) return value
  if (/^让平(?:\s*[（(]|$)/.test(value)) {
    return value.replace('让平', '走水')
  }
  const stripped = value.replace(/\/平|平\//g, '')
  return stripped.trim() || value
}
