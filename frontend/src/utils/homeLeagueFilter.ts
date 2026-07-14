/** Persist homepage sidebar league selection across detail / nav round-trips. */

const STORAGE_KEY = 'fa-home-selected-league'

export function readHomeLeagueFilter(): number | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (raw == null || raw === '' || raw === 'all') return null
    const id = Number(raw)
    return Number.isFinite(id) ? id : null
  } catch {
    return null
  }
}

export function writeHomeLeagueFilter(leagueId: number | null): void {
  try {
    sessionStorage.setItem(
      STORAGE_KEY,
      leagueId == null ? 'all' : String(leagueId),
    )
  } catch {
    // ignore quota / private mode
  }
}

export function homeRouteWithLeague(leagueId: number | null = readHomeLeagueFilter()) {
  return {
    name: 'home' as const,
    query: leagueId == null ? {} : { league: String(leagueId) },
  }
}
