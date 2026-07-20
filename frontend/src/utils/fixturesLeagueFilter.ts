/** Persist sidebar league selection per shell context (pre-match vs results). */

const PREMATCH_KEY = 'fa-prematch-selected-league'
const RESULTS_KEY = 'fa-results-selected-league'
const LEGACY_KEY = 'fa-home-selected-league'

export type FixturesRouteName = 'home' | 'predictions' | 'results'
export type FixturesShellContext = 'prematch' | 'results'

export function fixturesShellContext(
  routeName: FixturesRouteName | string | undefined,
): FixturesShellContext {
  return routeName === 'results' ? 'results' : 'prematch'
}

function storageKey(context: FixturesShellContext): string {
  return context === 'results' ? RESULTS_KEY : PREMATCH_KEY
}

export function readFixturesLeagueFilter(
  context: FixturesShellContext = 'prematch',
): number | null {
  try {
    let raw = sessionStorage.getItem(storageKey(context))
    if (context === 'prematch' && (raw == null || raw === '')) {
      raw = sessionStorage.getItem(LEGACY_KEY)
    }
    if (raw == null || raw === '' || raw === 'all') return null
    const id = Number(raw)
    return Number.isFinite(id) ? id : null
  } catch {
    return null
  }
}

export function writeFixturesLeagueFilter(
  leagueId: number | null,
  context: FixturesShellContext = 'prematch',
): void {
  try {
    sessionStorage.setItem(
      storageKey(context),
      leagueId == null ? 'all' : String(leagueId),
    )
  } catch {
    // ignore quota / private mode
  }
}

export const readHomeLeagueFilter = () => readFixturesLeagueFilter('prematch')
export const writeHomeLeagueFilter = (id: number | null) =>
  writeFixturesLeagueFilter(id, 'prematch')

export function fixturesRouteWithLeague(
  name: FixturesRouteName = 'home',
  leagueId?: number | null,
  extraQuery?: Record<string, string>,
) {
  const ctx = fixturesShellContext(name)
  const id = leagueId ?? readFixturesLeagueFilter(ctx)
  const query: Record<string, string> = { ...(extraQuery ?? {}) }
  if (id != null) query.league = String(id)
  return { name, query }
}

export function homeRouteWithLeague(
  leagueId: number | null = readFixturesLeagueFilter('prematch'),
) {
  return fixturesRouteWithLeague('home', leagueId)
}
