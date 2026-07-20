export type ResultsHitKey = 'result' | 'score' | 'ou' | 'btts'

const STORAGE_KEY = 'fa-results-page-state'

export interface ResultsPageState {
  date: string
  filterLeagueIds: number[]
  filterHitKeys: ResultsHitKey[]
  teamSearch: string
}

export function readResultsPageState(): ResultsPageState | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as ResultsPageState
    if (!parsed?.date || typeof parsed.date !== 'string') return null
    return {
      date: parsed.date,
      filterLeagueIds: Array.isArray(parsed.filterLeagueIds)
        ? parsed.filterLeagueIds.map(Number).filter((n) => Number.isFinite(n))
        : [],
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
