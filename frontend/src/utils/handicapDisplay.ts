export const HANDICAP_MISSING_LABEL = '缺少盘口数据分析'

export function isHandicapPending(text: string | null | undefined): boolean {
  const value = (text ?? '').trim()
  return !value || value.includes('缺少盘口') || value.includes('待分析')
}

/** Strip legacy line suffix: 让球负（-0.25）→ 让球负. New rows already omit the line. */
export function handicapLeanLabel(text: string | null | undefined): string {
  const value = (text ?? '').trim()
  if (!value) return ''
  return value.replace(/\s*[（(][+-]?\d+(?:\.\d+)?[）)]\s*$/, '')
}
