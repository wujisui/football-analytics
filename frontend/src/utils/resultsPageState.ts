export type ResultsHitKey = 'result' | 'score' | 'ou' | 'btts'

const STORAGE_KEY = 'fa-results-page-state'

export interface ResultsPageState {
  date: string
  filterHitKeys: ResultsHitKey[]
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
