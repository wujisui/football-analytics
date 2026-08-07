export const HANDICAP_MISSING_LABEL = '缺少盘口数据分析'

export function isHandicapPending(text: string | null | undefined): boolean {
  const value = (text ?? '').trim()
  return !value || value.includes('缺少盘口') || value.includes('待分析')
}

/**
 * Short pick for compact hit tags: 让球负（-1）→ 让球负.
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
