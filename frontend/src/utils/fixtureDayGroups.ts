import type { FixtureResponse } from '@/api/types'
import { formatScheduleDayFull } from '@/utils/format'

export type ScheduleDayGroup<
  T extends {
    fixture_date: string
    match_day: string
    match_day_offset?: number | null
  } = FixtureResponse,
> = {
  key: string
  label: string
  fixtures: T[]
}

export function scheduleDayLabel(dayKey: string, dayOffset?: number | null): string {
  const base = formatScheduleDayFull(dayKey)
  if (dayOffset === 0) return `今天 · ${base}`
  if (dayOffset === 1) return `明天 · ${base}`
  return base
}

/**
 * 【比赛】列表直接使用后端已按场地时区定稿的 ``match_day``。
 * 「今天/明天」读取后端相对查询窗口定稿的 offset，联赛筛选后也不会漂移。
 */
export function groupFixturesByScheduleDay<
  T extends {
    fixture_date: string
    match_day: string
    match_day_offset?: number | null
  },
>(
  fixtures: T[],
): ScheduleDayGroup<T>[] {
  const map = new Map<string, T[]>()
  for (const f of fixtures) {
    const key = f.match_day
    const bucket = map.get(key)
    if (bucket) bucket.push(f)
    else map.set(key, [f])
  }
  const entries = [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
  return entries.map(([key, list]) => ({
    key,
    label: scheduleDayLabel(key, list[0]?.match_day_offset),
    fixtures: list,
  }))
}
