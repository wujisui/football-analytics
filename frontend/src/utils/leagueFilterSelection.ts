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

/**
 * Sync / odds batch allow-list for a calendar day.
 *
 * Product rule: fixtures sync always ingests the full day. This helper only
 * scopes **odds** follow-up to default-checked primary leagues, plus any
 * secondary leagues the user explicitly checked.
 */
export function resolveSyncLeagueIds(
  options: LeagueFilterOption[],
  trackedIds: number[],
): number[] {
  if (!options.length) return []

  const tracked = new Set(trackedIds)
  const primaryDefaults = options
    .filter((o) => o.default_checked)
    .map((o) => o.league_id)
  const checkedPrimary = options
    .filter((o) => o.tier === 'configured' && tracked.has(o.league_id))
    .map((o) => o.league_id)
  const checkedSecondary = options
    .filter((o) => o.tier === 'extra' && tracked.has(o.league_id))
    .map((o) => o.league_id)

  const primaryScope = checkedPrimary.length ? checkedPrimary : primaryDefaults
  return [...new Set([...primaryScope, ...checkedSecondary])]
}
