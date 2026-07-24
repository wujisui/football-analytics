export const HANDICAP_MISSING_LABEL = '缺少盘口数据分析'

export function isHandicapPending(text: string | null | undefined): boolean {
  const value = (text ?? '').trim()
  return !value || value.includes('缺少盘口') || value.includes('待分析')
}
