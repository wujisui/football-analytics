/** Home schedule strip: today ± N calendar days + day-based list filters. */

export const HOME_DATE_RADIUS = 7

/** 计算器：UTC 比赛日今天 + 明天（与 API date= / 入库赛程日一致） */
export const PREMATCH_MATCH_DAY_SPAN = 2

const WEEKDAY_ZH = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
/** 计算器只展示未开赛；进行中已无法投注，归赛果列表。 */
const PREMATCH_STATUSES = new Set(['pending'])

function parseIso(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

export function isoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 浏览器本地日历「今天」（日期条展示用） */
export function todayDate(): string {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return isoDate(d)
}

/** UTC 赛程「今天」——场次比赛日基准（巴甲当晚仍属该 UTC 日） */
export function scheduleTodayDate(now = new Date()): string {
  return `${now.getUTCFullYear()}-${pad2(now.getUTCMonth() + 1)}-${pad2(now.getUTCDate())}`
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

/** Calculator prematch list: pending only. Live + finished belong on 赛果. */
export function isPrematchFixtureVisible(status: string): boolean {
  return PREMATCH_STATUSES.has(status.toLowerCase())
}

export function predictionsDayCountLabel(count: number): string {
  return `未开赛 ${count} 场`
}

export function isScheduleFutureDay(day: string, today: string = todayDate()): boolean {
  return day > today
}

/** 计算器可见的 UTC 比赛日集合 */
export function prematchAllowedMatchDays(
  scheduleToday: string = scheduleTodayDate(),
): Set<string> {
  const days = new Set<string>()
  for (let i = 0; i < PREMATCH_MATCH_DAY_SPAN; i += 1) {
    days.add(addCalendarDays(scheduleToday, i))
  }
  return days
}

export function isPrematchMatchDay(
  matchDay: string,
  scheduleToday: string = scheduleTodayDate(),
): boolean {
  return prematchAllowedMatchDays(scheduleToday).has(matchDay)
}

/** 拉取计算器列表：从 UTC 今天起共 2 个比赛日 */
export function prematchFetchParams(now = new Date()): {
  date: string
  days: number
} {
  return { date: scheduleTodayDate(now), days: PREMATCH_MATCH_DAY_SPAN }
}
