import type { RouteLocationRaw } from 'vue-router'

import {
  fixturesRouteWithLeague,
  homeRouteWithLeague,
} from '@/utils/fixturesLeagueFilter'

export type DetailFrom = 'home' | 'results' | 'predictions' | 'favorites'

export type DetailTab = 'record' | 'stats' | 'lineup' | 'briefing' | 'prediction'

/** Tooltip / aria-label when opening fixture detail from list score or VS. */
export const FIXTURE_DETAIL_TOOLTIP = '查看详细分析'

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
  if (from === 'results') return '赛果'
  if (from === 'predictions') return '预测'
  if (from === 'favorites') return '收藏'
  return '赛前赛事'
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
    return homeRouteWithLeague()
  }
  // Omit leagueId → restore session filter; pass id for「联赛」crumb.
  if (opts && 'leagueId' in opts) {
    return homeRouteWithLeague(opts.leagueId ?? null)
  }
  return homeRouteWithLeague()
}
