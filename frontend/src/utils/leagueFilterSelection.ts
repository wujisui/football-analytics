import type { LeagueFilterOption } from '@/api/leagues'

/** Resolve checked league ids from options + stored/tracked preference. */
export function resolveTrackedSelection(
  options: LeagueFilterOption[],
  trackedIds: number[],
): number[] {
  if (!options.length) return []

  const allow = new Set(options.map((o) => o.league_id))
  const defaults = options.filter((o) => o.default_checked).map((o) => o.league_id)
  const preferred = trackedIds.filter((id) => allow.has(id))

  if (preferred.length) return preferred
  return defaults
}
