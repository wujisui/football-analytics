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
  if (defaults.length) return defaults
  // 该日一个热门联赛都没有（赛程刚入库、冷门日）：回落到当天全部联赛。
  // 否则勾选为空，列表在 `!leagueIds.length` 处直接发布空数组，
  // 明明有非热门比赛却整页空白。
  return [...allow]
}
