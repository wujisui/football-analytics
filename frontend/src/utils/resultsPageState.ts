/** Accuracy metric keys; day-stats hit counts can toggle list filter by key. */
export type ResultsHitKey =
  | 'result'
  | 'auto_pick'
  | 'score'
  | 'ou'
  | 'btts'
  | 'handicap'

export const RESULTS_HIT_OPTIONS: { key: ResultsHitKey; label: string }[] = [
  { key: 'result', label: '推荐结果' },
  { key: 'auto_pick', label: '每日推荐' },
  { key: 'score', label: '比分' },
  { key: 'ou', label: '大小球' },
  { key: 'btts', label: '双方进球' },
  { key: 'handicap', label: '让球胜平负' },
]

/** Phone panes on 赛程 (results day): list (+ day-stats modal) | history+chart. */
export type ResultsPhoneTab = 'list' | 'history'

export const RESULTS_PHONE_TABS: ResultsPhoneTab[] = ['list', 'history']

const STORAGE_KEY = 'fa-results-page-state'
const VALID_PHONE_TABS = new Set<string>(RESULTS_PHONE_TABS)

export interface ResultsPageState {
  date: string
  phoneTab: ResultsPhoneTab
}

function normalizePhoneTab(raw: unknown): ResultsPhoneTab {
  const value = String(raw ?? '')
  if (VALID_PHONE_TABS.has(value)) return value as ResultsPhoneTab
  // Migrate old 4-tab ids
  if (value === 'day') return 'list'
  if (value === 'chart') return 'history'
  return 'list'
}

export function readResultsPageState(): ResultsPageState | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<ResultsPageState>
    if (!parsed?.date || typeof parsed.date !== 'string') return null
    return {
      date: parsed.date,
      phoneTab: normalizePhoneTab(parsed.phoneTab),
    }
  } catch {
    return null
  }
}

export function writeResultsPageState(state: ResultsPageState): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    /* ignore */
  }
}
