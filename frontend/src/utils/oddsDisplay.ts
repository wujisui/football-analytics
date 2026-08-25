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

function capturedAtMs(odds: OddsLike): number | null {
  const at = odds && 'captured_at' in odds ? odds.captured_at : null
  if (!at) return null
  const ms = Date.parse(at)
  return Number.isFinite(ms) ? ms : null
}

/**
 * 初盘是否值得单独展示，只看采集时间：严格早于即时盘才算两份盘口。
 *
 * 初盘可能刚由当前这份冻结或替换（主庄开盘后顶掉次级庄兜底的那份），此时两者
 * 采集时间相同、内容也相同，按即时盘展示一份即可。判定不逐档比水位：盘口没动
 * 但确实是后一次采集的，仍然是即时盘。旧行缺采集时间时无从判定，同样只展示一份。
 */
export function isOpeningDistinct(opening: OddsLike, current: OddsLike): boolean {
  if (!hasOddsMarkets(opening)) return false
  if (!hasOddsMarkets(current)) return true
  const openingMs = capturedAtMs(opening)
  const currentMs = capturedAtMs(current)
  if (openingMs == null || currentMs == null) return false
  return openingMs < currentMs
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
