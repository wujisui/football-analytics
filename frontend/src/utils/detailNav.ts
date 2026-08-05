import type { RouteLocationRaw } from 'vue-router'

import { findFavoriteListFixture } from '@/composables/useFavoriteFixtures'
import { findPrematchListFixture } from '@/composables/useHomeFixtures'
import { findResultsListFixture } from '@/composables/useResultsLeagues'
import {
  fixturesRouteWithLeague,
  homeRouteWithLeague,
} from '@/utils/fixturesLeagueFilter'

export type DetailFrom = 'home' | 'results' | 'predictions' | 'favorites'

export type DetailTab = 'record' | 'stats' | 'lineup' | 'briefing' | 'prediction'

/** Fields BasicInfo needs before full /analysis arrives. */
export type DetailCrumbFixture = {
  league_id: number
  league_name: string
  home_team_name: string
  away_team_name: string
  home_rank?: number | null
  away_rank?: number | null
  home_goals?: number | null
  away_goals?: number | null
}

/** Tooltip / aria-label when opening fixture detail from list score or VS. */
export const FIXTURE_DETAIL_TOOLTIP = '查看详细分析（统计）'

export function parseDetailFrom(raw: unknown): DetailFrom {
  if (raw === 'results' || raw === 'predictions' || raw === 'favorites') return raw
  return 'home'
}

export function parseDetailTab(raw: unknown): DetailTab | null {
  if (
    raw === 'record' ||
    raw === 'stats' ||
    raw === 'lineup' ||
    raw === 'briefing' ||
    raw === 'prediction'
  ) {
    return raw
  }
  return null
}

export function fixtureDetailRoute(
  fixtureId: number,
  opts?: { from?: DetailFrom; tab?: DetailTab; date?: string | null },
): RouteLocationRaw {
  const query: Record<string, string> = {}
  if (opts?.from) query.from = opts.from
  if (opts?.tab) query.tab = opts.tab
  if (opts?.date) query.date = opts.date
  return {
    name: 'fixture-detail',
    params: { fixtureId: String(fixtureId) },
    query,
  }
}

export function detailRootLabel(from: DetailFrom): string {
  if (from === 'results') return '赛程'
  if (from === 'predictions') return '计算器'
  if (from === 'favorites') return '收藏'
  return '即时'
}

/**
 * Prefer list-row caches so the breadcrumb can render immediately on enter.
 * Deep links with empty caches return null (chrome still shows root label).
 */
export function peekDetailCrumb(fixtureId: number): DetailCrumbFixture | null {
  if (!Number.isFinite(fixtureId)) return null
  const hit =
    findPrematchListFixture(fixtureId) ??
    findResultsListFixture(fixtureId) ??
    findFavoriteListFixture(fixtureId)
  if (!hit) return null
  return {
    league_id: hit.league_id,
    league_name: hit.league_name,
    home_team_name: hit.home_team_name,
    away_team_name: hit.away_team_name,
    home_rank: 'home_rank' in hit ? hit.home_rank : null,
    away_rank: 'away_rank' in hit ? hit.away_rank : null,
    home_goals: hit.home_goals,
    away_goals: hit.away_goals,
  }
}

/** Breadcrumb / page-header back target based on how the user opened detail. */
export function detailBackRoute(
  from: DetailFrom,
  opts?: { date?: string | null; leagueId?: number | null },
): RouteLocationRaw {
  if (from === 'results') {
    const date = opts?.date
    const extra =
      typeof date === 'string' && date ? { date } : undefined
    return fixturesRouteWithLeague(
      'results',
      opts && 'leagueId' in opts ? opts.leagueId ?? null : undefined,
      extra,
    )
  }
  if (from === 'predictions') {
    return fixturesRouteWithLeague('predictions')
  }
  if (from === 'favorites') {
    return { name: 'favorites' }
  }
  // Omit leagueId → restore session filter; pass id for「联赛」crumb.
  if (opts && 'leagueId' in opts) {
    return homeRouteWithLeague(opts.leagueId ?? null)
  }
  return homeRouteWithLeague()
}
