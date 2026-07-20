import type { FixtureOddsSnippet, LineOdds, OddsPackage, FixtureResponse } from '@/api/types'

export type OddsLike = FixtureOddsSnippet | OddsPackage | null | undefined

export function ahLinesOf(market?: LineOdds | null) {
  if (!market) return []
  if (market.lines?.length) {
    return market.lines.filter((l) => l.line != null && l.line !== '')
  }
  if (market.line != null && market.line !== '') {
    return [{ line: market.line, home: market.home, away: market.away }]
  }
  return []
}

export function hasOddsMarkets(odds: OddsLike): boolean {
  if (!odds) return false
  if ('available' in odds && odds.available === false) return false
  return !!(
    odds.match_winner ||
    odds.goals_ou ||
    ahLinesOf(odds.asian_handicap).length
  )
}

/** Build list-card snippet from detail odds package. */
export function oddsPackageToSnippet(
  odds: OddsPackage | null | undefined,
): FixtureOddsSnippet | null {
  if (!odds?.available) return null
  return {
    available: true,
    match_winner: odds.match_winner,
    asian_handicap: odds.asian_handicap,
    goals_ou: odds.goals_ou,
  }
}

/** Prefer list snippet; fall back to detail package odds. */
export function oddsSnippetFromFixture(
  fixture: Pick<FixtureResponse, 'odds_snippet' | 'analysis'>,
): FixtureOddsSnippet | null {
  return (
    fixture.odds_snippet ??
    oddsPackageToSnippet(fixture.analysis?.package?.odds ?? null)
  )
}
