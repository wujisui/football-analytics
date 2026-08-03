export type ResultsHitKey =
  | 'result'
  | 'single_result'
  | 'score'
  | 'ou'
  | 'btts'
  | 'handicap'

export const RESULTS_HIT_OPTIONS: { key: ResultsHitKey; label: string }[] = [
  { key: 'result', label: '推荐结果' },
  { key: 'single_result', label: '胜平负单选' },
  { key: 'score', label: '比分' },
  { key: 'ou', label: '大小球' },
  { key: 'btts', label: '双方进球' },
  { key: 'handicap', label: '让球胜平负' },
]

export const RESULTS_ALL_HIT_KEYS = RESULTS_HIT_OPTIONS.map((o) => o.key)

/** Phone panes on 赛程 (results day): list (+ day-stats modal) | history+chart. */
export type ResultsPhoneTab = 'list' | 'history'

export const RESULTS_PHONE_TABS: ResultsPhoneTab[] = ['list', 'history']

const STORAGE_KEY = 'fa-results-page-state'
const VALID_HIT_KEYS = new Set<string>(RESULTS_ALL_HIT_KEYS)
const VALID_PHONE_TABS = new Set<string>(RESULTS_PHONE_TABS)

export interface ResultsPageState {
  date: string
  filterHitKeys: ResultsHitKey[]
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
    const filterHitKeys = Array.isArray(parsed.filterHitKeys)
      ? parsed.filterHitKeys.filter(
          (key): key is ResultsHitKey => VALID_HIT_KEYS.has(key),
        )
      : []
    return {
      date: parsed.date,
      filterHitKeys,
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
