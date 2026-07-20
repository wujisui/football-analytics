/** Home schedule strip: today ± N calendar days + day-based list filters. */

export const HOME_DATE_RADIUS = 7

const WEEKDAY_ZH = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const FINISHED_STATUSES = new Set(['finished', 'cancelled', 'postponed'])
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

export type HomeDayKind = 'past' | 'today' | 'future'

export function homeDayKind(day: string, today: string = todayDate()): HomeDayKind {
  if (day < today) return 'past'
  if (day > today) return 'future'
  return 'today'
}

/** Which fixtures to show on Home for the selected calendar day. */
export function isHomeFixtureVisible(
  status: string,
  day: string,
  today: string = todayDate(),
): boolean {
  const s = status.toLowerCase()
  const kind = homeDayKind(day, today)
  if (kind === 'past') return FINISHED_STATUSES.has(s)
  if (kind === 'future') return s === 'pending'
  return s === 'pending' || s === 'live' || s === 'finished'
}

export function homeDayStatusHint(kind: HomeDayKind): string {
  if (kind === 'past') return '完场'
  if (kind === 'future') return '未开赛'
  return '当日'
}

export function homeDayCountLabel(kind: HomeDayKind, count: number): string {
  if (kind === 'past') return `完场 ${count} 场`
  if (kind === 'future') return `未开赛 ${count} 场`
  return `当日 ${count} 场`
}

export function isPredictionsFixtureVisible(status: string): boolean {
  return ACTIVE_STATUSES.has(status.toLowerCase())
}

export function predictionsDayCountLabel(count: number): string {
  return `未完赛 ${count} 场`
}

export function resultsDayCountLabel(count: number): string {
  return `完场 ${count} 场`
}
