/** Persist sidebar league selection per shell context (pre-match vs results). */

const PREMATCH_KEY = 'fa-prematch-selected-league'
const RESULTS_KEY = 'fa-results-selected-league'
const LEGACY_KEY = 'fa-home-selected-league'

export type FixturesRouteName = 'predictions' | 'results'
export type FixturesShellContext = 'prematch' | 'results'

export function parseFixturesLeagueFilter(raw: unknown): number | null {
  const value = Array.isArray(raw) ? raw[0] : raw
  if (value == null || value === '' || value === 'all') return null
  const id = Number(value)
  return Number.isFinite(id) ? id : null
}

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
    return parseFixturesLeagueFilter(raw)
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

export function fixturesRouteWithLeague(
  name: FixturesRouteName = 'predictions',
  leagueId?: number | null,
  extraQuery?: Record<string, string>,
) {
  const ctx = fixturesShellContext(name)
  const id = leagueId ?? readFixturesLeagueFilter(ctx)
  const query: Record<string, string> = { ...(extraQuery ?? {}) }
  if (id != null) query.league = String(id)
  return { name, query }
}

export function predictionsRouteWithLeague(
  leagueId: number | null = readFixturesLeagueFilter('prematch'),
) {
  return fixturesRouteWithLeague('predictions', leagueId)
}
