/** Home schedule strip: today ± N calendar days + day-based list filters. */

export const HOME_DATE_RADIUS = 7

const WEEKDAY_ZH = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const ACTIVE_STATUSES = new Set(['pending', 'live'])

function parseIso(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function isoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function todayDate(): string {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return isoDate(d)
}

/** Calendar day before today (local). */
export function yesterdayDate(): string {
  return addCalendarDays(todayDate(), -1)
}

/** Clamp calendar day to today when picking prematch dates. */
export function clampToToday(iso: string, today: string = todayDate()): string {
  return iso < today ? today : iso
}

/** Clamp calendar day to today when picking results dates (no future). */
export function clampToLatest(iso: string, today: string = todayDate()): string {
  return iso > today ? today : iso
}

export function addCalendarDays(iso: string, delta: number): string {
  const d = parseIso(iso)
  d.setDate(d.getDate() + delta)
  return isoDate(d)
}

export interface HomeDateTab {
  iso: string
  topLabel: string
  bottomLabel: string
}

export function buildHomeDateTabs(
  today: string = todayDate(),
  radius = HOME_DATE_RADIUS,
): HomeDateTab[] {
  const tabs: HomeDateTab[] = []
  for (let offset = -radius; offset <= radius; offset += 1) {
    const iso = addCalendarDays(today, offset)
    const d = parseIso(iso)
    tabs.push({
      iso,
      topLabel: offset === 0 ? '今天' : WEEKDAY_ZH[d.getDay()],
      bottomLabel: `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`,
    })
  }
  return tabs
}

/** Prematch lists (即时 / 预测): unfinished only. Finished matches belong on 赛果. */
export function isPrematchFixtureVisible(status: string): boolean {
  return ACTIVE_STATUSES.has(status.toLowerCase())
}

export function predictionsDayCountLabel(count: number): string {
  return `未完赛 ${count} 场`
}

export function resultsDayCountLabel(count: number): string {
  return `完场 ${count} 场`
}

export function scheduleDayCountLabel(count: number): string {
  return `未开赛 ${count} 场`
}

export function isScheduleFutureDay(day: string, today: string = todayDate()): boolean {
  return day > today
}
