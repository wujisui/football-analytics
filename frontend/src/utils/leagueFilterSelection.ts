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
 * Product rule: batch fixtures + pre-match odds for **default-checked primary
 * leagues**; secondary leagues join only when the user explicitly checks them.
 * If primary checks were cleared by stale state, fall back to that day's defaults.
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
