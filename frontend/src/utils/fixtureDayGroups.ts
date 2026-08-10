import type { FixtureResponse } from '@/api/types'
import { formatScheduleDayFull, toScheduleDayKey } from '@/utils/format'
import { addCalendarDays, scheduleTodayDate } from '@/utils/homeDateStrip'

export type ScheduleDayGroup<T extends { fixture_date: string } = FixtureResponse> = {
  key: string
  label: string
  fixtures: T[]
}

export function scheduleDayLabel(dayKey: string): string {
  const scheduleToday = scheduleTodayDate()
  const base = formatScheduleDayFull(dayKey)
  if (dayKey === scheduleToday) return `今天 · ${base}`
  if (dayKey === addCalendarDays(scheduleToday, 1)) return `明天 · ${base}`
  return base
}

/** Group fixtures by UTC schedule day (API ``date=`` / 入库赛程日). */
export function groupFixturesByScheduleDay<T extends { fixture_date: string }>(
  fixtures: T[],
): ScheduleDayGroup<T>[] {
  const map = new Map<string, T[]>()
  for (const f of fixtures) {
    const key = toScheduleDayKey(f.fixture_date)
    const bucket = map.get(key)
    if (bucket) bucket.push(f)
    else map.set(key, [f])
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, list]) => ({
      key,
      label: scheduleDayLabel(key),
      fixtures: list,
    }))
}
