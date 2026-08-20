export type HandicapRuleset = 'asian' | 'jc'

export const HANDICAP_RULESET_STORAGE_KEY = 'fa-handicap-ruleset'

export const DEFAULT_HANDICAP_RULESET: HandicapRuleset = 'asian'

export function parseHandicapRuleset(value: string | null | undefined): HandicapRuleset {
  const text = (value || '').trim().toLowerCase()
  if (text === 'jc' || text === 'jingcai' || text === 'lottery') return 'jc'
  return 'asian'
}

/**
 * 竞彩只挂整数让球线：非整数按绝对值向上取整（-0.25/-0.5/-0.75 → -1）。
 * 与后端 `ah_features.jc_handicap_line` 同一口径；赛前列表接口不带口径参数，
 * 所以前端也要有一份。
 */
export function jcHandicapLine(line: number): number {
  if (!Number.isFinite(line)) return line
  const magnitude = Math.ceil(Math.abs(line) - 1e-9)
  if (magnitude <= 0) return 0
  return line > 0 ? magnitude : -magnitude
}

/** 有符号让球线文案：主让为负、客让为正、平手为 0。 */
export function formatSignedHandicapLine(line: number): string {
  if (!Number.isFinite(line)) return ''
  if (Math.abs(line) < 1e-9) return '0'
  return line > 0 ? `+${line}` : String(line)
}

export function storedHandicapRuleset(): HandicapRuleset {
  try {
    return parseHandicapRuleset(localStorage.getItem(HANDICAP_RULESET_STORAGE_KEY))
  } catch {
    return DEFAULT_HANDICAP_RULESET
  }
}
