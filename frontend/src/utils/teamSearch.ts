import { fuzzyMatchAny } from '@/utils/fuzzySearch'

/** Match fixtures by home/away club display name (fuzzy). */

export interface TeamNamedFixture {
  home_team_name?: string | null
  away_team_name?: string | null
}

export function fixtureMatchesTeamQuery(
  fixture: TeamNamedFixture,
  query: string,
): boolean {
  return fuzzyMatchAny(query, [
    fixture.home_team_name,
    fixture.away_team_name,
  ])
}

export function filterByTeamQuery<T extends TeamNamedFixture>(
  list: readonly T[],
  query: string,
): T[] {
  const q = query.trim()
  if (!q) return [...list]
  return list.filter((item) => fixtureMatchesTeamQuery(item, q))
}

export function teamSearchEmptyHint(query: string): string {
  const q = query.trim()
  return q ? `未找到包含「${q}」的俱乐部` : ''
}
