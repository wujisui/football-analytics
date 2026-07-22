export type ResultsHitKey = 'result' | 'score' | 'ou' | 'btts'

export const RESULTS_HIT_OPTIONS: { key: ResultsHitKey; label: string }[] = [
  { key: 'score', label: '比分' },
  { key: 'result', label: '胜平负' },
  { key: 'ou', label: '大小球' },
  { key: 'btts', label: '双方进球' },
]

export const RESULTS_ALL_HIT_KEYS = RESULTS_HIT_OPTIONS.map((o) => o.key)

export interface ResultsFilterConfirm {
  hitKeys: ResultsHitKey[]
  hideWithoutPrediction: boolean
}

const STORAGE_KEY = 'fa-results-page-state'

export interface ResultsPageState {
  date: string
  filterHitKeys: ResultsHitKey[]
  hideWithoutPrediction?: boolean
  teamSearch: string
}

export function readResultsPageState(): ResultsPageState | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as ResultsPageState & { filterLeagueIds?: number[] }
    if (!parsed?.date || typeof parsed.date !== 'string') return null
    return {
      date: parsed.date,
      filterHitKeys: Array.isArray(parsed.filterHitKeys)
        ? (parsed.filterHitKeys as ResultsHitKey[])
        : [],
      hideWithoutPrediction: parsed.hideWithoutPrediction === true,
      teamSearch: typeof parsed.teamSearch === 'string' ? parsed.teamSearch : '',
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
