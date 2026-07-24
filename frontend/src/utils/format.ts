import type { ProbabilitiesResponse } from '@/api/types'

type NaiveTagType = 'default' | 'success' | 'warning' | 'error' | 'info'

const ZH_LOCALE = 'zh-CN'
const FLAT_PROB_EPS = 0.02

const RESULT_ZH: Record<string, string> = {
  W: '胜',
  WIN: '胜',
  HOME: '胜',
  D: '平',
  DRAW: '平',
  L: '负',
  LOSS: '负',
  AWAY: '负',
}

const STATUS_SHORT_LABEL: Record<string, string> = {
  FT: '完场',
  AET: '完场',
  PEN: '完场',
  ET: '完场',
}

const STATUS_META: Record<string, { label: string; tag: NaiveTagType }> = {
  pending: { label: '未开始', tag: 'info' },
  live: { label: '进行中', tag: 'warning' },
  finished: { label: '完场', tag: 'success' },
  postponed: { label: '延期', tag: 'error' },
  cancelled: { label: '取消', tag: 'error' },
}

const LEAGUE_COLORS = [
  '#2080f0',
  '#18a058',
  '#f0a020',
  '#d03050',
  '#8a2be2',
  '#0e7c86',
  '#c2410c',
  '#4338ca',
]

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

function invalidDateFallback(raw: string, sliceLen = 10): string {
  return raw.slice(0, sliceLen) || raw
}

/** Parse API datetime: naive strings are treated as UTC (API-Sports kickoff). */
export function parseApiDate(dateStr: string | Date): Date {
  if (dateStr instanceof Date) return dateStr
  const raw = String(dateStr).trim()
  if (!raw) return new Date(NaN)

  // Already has timezone (Z or ±hh:mm)
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(raw)) {
    return new Date(raw)
  }

  // "2026-07-09T14:00:00" or "2026-07-09 14:00:00" → UTC
  const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T')
  return new Date(`${normalized}Z`)
}

/** Local calendar day key for filters / grouping: `2026-07-09`. */
export function toLocalDayKey(dateStr: string | Date): string {
  const d = dateStr instanceof Date ? dateStr : parseApiDate(dateStr)
  if (Number.isNaN(d.getTime())) {
    return typeof dateStr === 'string' ? invalidDateFallback(dateStr) : ''
  }
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

/**
 * Schedule calendar day (UTC date of kickoff), aligned with `/fixtures/today?date=`.
 * Home lists fixtures by this day; local display may show the next calendar date
 * for late UTC kickoffs (e.g. 03:00 北京时间仍归属前一日赛程).
 */
export function toScheduleDayKey(dateStr: string | Date): string {
  const d = dateStr instanceof Date ? dateStr : parseApiDate(dateStr)
  if (Number.isNaN(d.getTime())) {
    return typeof dateStr === 'string' ? invalidDateFallback(dateStr) : ''
  }
  return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())}`
}

function tzOffsetLabel(date: Date): string {
  const offsetMin = -date.getTimezoneOffset()
  const sign = offsetMin >= 0 ? '+' : '-'
  const abs = Math.abs(offsetMin)
  return `UTC${sign}${pad2(Math.floor(abs / 60))}:${pad2(abs % 60)}`
}

function formatLocaleDate(
  dateStr: string,
  options: Intl.DateTimeFormatOptions,
): string {
  const d = parseApiDate(dateStr)
  if (Number.isNaN(d.getTime())) return dateStr
  return d.toLocaleDateString(ZH_LOCALE, options)
}

function formatLocaleTime(
  dateStr: string,
  options: Intl.DateTimeFormatOptions,
): string {
  const d = parseApiDate(dateStr)
  if (Number.isNaN(d.getTime())) return dateStr
  return d.toLocaleTimeString(ZH_LOCALE, options)
}

/** Local kickoff: 2026-07-09 22:00 (UTC+08:00) */
export function formatDateTime(dateStr: string): string {
  const d = parseApiDate(dateStr)
  if (Number.isNaN(d.getTime())) return dateStr
  const date = d.toLocaleDateString(ZH_LOCALE, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
  const time = d.toLocaleTimeString(ZH_LOCALE, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return `${date} ${time} (${tzOffsetLabel(d)})`
}

/** Local date: 07-09 周四 */
export function formatDate(dateStr: string): string {
  return formatLocaleDate(dateStr, {
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
  })
}

/** Local time: 22:00 */
export function formatTime(dateStr: string): string {
  return formatLocaleTime(dateStr, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

/** Compact local date for stats tables: 26.07.09 */
export function formatDateYyMmDd(dateStr: string): string {
  const d = parseApiDate(dateStr)
  if (Number.isNaN(d.getTime())) {
    const m = String(dateStr).match(/(\d{4})-(\d{2})-(\d{2})/)
    if (!m) return invalidDateFallback(dateStr)
    return `${m[1].slice(2)}.${m[2]}.${m[3]}`
  }
  return `${String(d.getFullYear()).slice(2)}.${pad2(d.getMonth() + 1)}.${pad2(d.getDate())}`
}

/** W/D/L or win/draw/loss → 胜/平/负 */
export function resultToZh(code?: string | null): string {
  if (!code) return '—'
  const raw = String(code).trim()
  if (raw === '胜' || raw === '平' || raw === '负') return raw
  return RESULT_ZH[raw.toUpperCase()] ?? code
}

/** Form string "WWDWL" → ["胜","胜","平","负","胜"] */
export function formCharsZh(form?: string, limit = 5): string[] {
  if (!form) return []
  return form
    .replace(/[^WDL胜平负]/gi, '')
    .split('')
    .slice(0, limit)
    .map((ch) => resultToZh(ch))
}

export function formCharClass(zh: string): string {
  if (zh === '胜') return 'w'
  if (zh === '平') return 'd'
  if (zh === '负') return 'l'
  return ''
}

/** Format rank like commercial apps: [5] */
export function rankBracket(rank?: number | null): string {
  if (rank == null || Number.isNaN(Number(rank))) return ''
  return `[${rank}]`
}

export function formatOdd(value?: string | number | null): string {
  if (value == null || value === '') return '—'
  return String(value)
}

export function toPercent(prob: number, digits = 0): string {
  return `${(prob * 100).toFixed(digits)}%`
}

/** True when API has real 1X2 probabilities (not placeholder / missing). */
export function hasRealProbabilities(
  probabilities?: ProbabilitiesResponse | null,
  recommendation?: string | null,
): boolean {
  if (recommendation === '待分析') return false
  if (!probabilities || probabilities.available === false) return false
  const h = probabilities.home_win_prob
  const d = probabilities.draw_prob
  const a = probabilities.away_win_prob
  if (h == null || d == null || a == null) return false
  // Guard against legacy flat 1/3 payloads.
  const flat =
    Math.abs(h - 1 / 3) < FLAT_PROB_EPS &&
    Math.abs(d - 1 / 3) < FLAT_PROB_EPS &&
    Math.abs(a - 1 / 3) < FLAT_PROB_EPS
  return !flat
}

export function statusLabel(status: string, statusShort?: string | null): string {
  const short = (statusShort || '').toUpperCase()
  if (short && STATUS_SHORT_LABEL[short]) return STATUS_SHORT_LABEL[short]
  return STATUS_META[status.toLowerCase()]?.label || status
}

export function statusTagType(
  status: string,
  statusShort?: string | null,
): NaiveTagType {
  const short = (statusShort || '').toUpperCase()
  if (short && STATUS_SHORT_LABEL[short]) {
    return STATUS_META.finished?.tag ?? 'default'
  }
  return STATUS_META[status.toLowerCase()]?.tag ?? 'default'
}

/** Results cards consistently mark finished fixtures as red. */
export function resultStatusTagType(
  status: string,
  statusShort?: string | null,
): NaiveTagType {
  if (status.toLowerCase() === 'finished') return 'error'
  return statusTagType(status, statusShort)
}

export function leagueTagColor(leagueId: number): string {
  return LEAGUE_COLORS[Math.abs(leagueId) % LEAGUE_COLORS.length]
}
