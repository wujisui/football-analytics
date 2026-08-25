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

/** Stable fingerprint of display markets (ignore role / captured_at). */
export function oddsMarketsFingerprint(odds: OddsLike): string {
  if (!hasOddsMarkets(odds)) return ''
  const mw = odds?.match_winner
  const ou = odds?.goals_ou
  const btts = odds && 'both_teams_score' in odds ? odds.both_teams_score : null
  return JSON.stringify({
    mw: mw ? [mw.home, mw.draw, mw.away] : null,
    ou: ou
      ? [ou.line, ou.home, ou.away, (ou.lines ?? []).map((l) => [l.line, l.home, l.away])]
      : null,
    ah: ahLinesOf(odds?.asian_handicap).map((l) => [l.line, l.home, l.away]),
    btts: btts ? [btts.home, btts.away] : null,
  })
}

/**
 * True when 即时盘 is meaningfully later/different than 初盘.
 * Same first-capture board should not render as two identical cards.
 */
export function isDistinctCurrentOdds(
  current: OddsLike,
  opening: OddsLike,
): boolean {
  if (!hasOddsMarkets(current)) return false
  if (!hasOddsMarkets(opening)) return true
  if (oddsMarketsFingerprint(current) !== oddsMarketsFingerprint(opening)) {
    return true
  }
  const cAt = current && 'captured_at' in current ? current.captured_at : null
  const oAt = opening && 'captured_at' in opening ? opening.captured_at : null
  if (cAt && oAt) {
    const cMs = Date.parse(cAt)
    const oMs = Date.parse(oAt)
    if (Number.isFinite(cMs) && Number.isFinite(oMs) && cMs > oMs) return true
  }
  return false
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
    both_teams_score: odds.both_teams_score,
    captured_at: odds.captured_at ?? null,
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

/** Prefer list opening snippet; fall back to detail package frozen opening odds. */
export function openingOddsSnippetFromFixture(
  fixture: Pick<FixtureResponse, 'odds_opening_snippet' | 'analysis'>,
): FixtureOddsSnippet | null {
  return (
    fixture.odds_opening_snippet ??
    oddsPackageToSnippet(fixture.analysis?.package?.odds_opening ?? null)
  )
}

/** Merge detail response into a list row, including score refreshed on detail click. */
export function mergeDetailIntoListFixture(
  prev: FixtureResponse,
  detail: FixtureResponse,
): FixtureResponse {
  const snippet = oddsSnippetFromFixture(detail) ?? prev.odds_snippet
  const openingSnippet =
    openingOddsSnippetFromFixture(detail) ?? prev.odds_opening_snippet
  return {
    ...prev,
    status: detail.status,
    home_goals: detail.home_goals ?? prev.home_goals,
    away_goals: detail.away_goals ?? prev.away_goals,
    home_rank: detail.home_rank ?? prev.home_rank,
    away_rank: detail.away_rank ?? prev.away_rank,
    odds_snippet: snippet,
    odds_opening_snippet: openingSnippet,
    analysis: detail.analysis ?? prev.analysis,
  }
}
