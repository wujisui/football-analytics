import type { LeagueFilterOption } from '@/api/leagues'

/** Resolve checked league ids from options + stored/tracked preference. */
export function resolveTrackedSelection(
  options: LeagueFilterOption[],
  trackedIds: number[],
): number[] {
  if (!options.length) return []

  const allow = new Set(options.map((o) => o.league_id))
  const defaults = options.filter((o) => o.default_checked).map((o) => o.league_id)
  const configuredIds = options
    .filter((o) => o.tier === 'configured')
    .map((o) => o.league_id)
  const preferred = trackedIds.filter((id) => allow.has(id))

  if (
    configuredIds.length > 0 &&
    !configuredIds.some((id) => preferred.includes(id))
  ) {
    return defaults
  }
  if (preferred.length) return preferred
  return defaults
}
