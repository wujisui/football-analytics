import type { RouteLocationRaw } from 'vue-router'

import { homeRouteWithLeague } from '@/utils/homeLeagueFilter'

export type DetailFrom = 'home' | 'results' | 'predictions'

export function parseDetailFrom(raw: unknown): DetailFrom {
  if (raw === 'results' || raw === 'predictions') return raw
  return 'home'
}

export function detailRootLabel(from: DetailFrom): string {
  if (from === 'results') return '赛果'
  if (from === 'predictions') return '预测'
  return '赛前赛事'
}

/** Breadcrumb / page-header back target based on how the user opened detail. */
export function detailBackRoute(
  from: DetailFrom,
  opts?: { date?: string | null; leagueId?: number | null },
): RouteLocationRaw {
  if (from === 'results') {
    const date = opts?.date
    return {
      name: 'results',
      query: typeof date === 'string' && date ? { date } : {},
    }
  }
  if (from === 'predictions') {
    return { name: 'predictions' }
  }
  // Omit leagueId → restore session filter; pass id for「联赛」crumb.
  if (opts && 'leagueId' in opts) {
    return homeRouteWithLeague(opts.leagueId ?? null)
  }
  return homeRouteWithLeague()
}
