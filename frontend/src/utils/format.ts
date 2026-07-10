import type { ProbabilitiesResponse } from '@/api/types'

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

function tzOffsetLabel(date: Date): string {
  const offsetMin = -date.getTimezoneOffset()
  const sign = offsetMin >= 0 ? '+' : '-'
  const abs = Math.abs(offsetMin)
  const hh = String(Math.floor(abs / 60)).padStart(2, '0')
  const mm = String(abs % 60).padStart(2, '0')
  return `UTC${sign}${hh}:${mm}`
}

/** Local kickoff: 2026-07-09 22:00 (UTC+08:00) */
export function formatDateTime(dateStr: string): string {
  const d = parseApiDate(dateStr)
  if (Number.isNaN(d.getTime())) return dateStr
  const date = d.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
  const time = d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return `${date} ${time} (${tzOffsetLabel(d)})`
}

/** Local date: 07-09 周四 */
export function formatDate(dateStr: string): string {
  const d = parseApiDate(dateStr)
  if (Number.isNaN(d.getTime())) return dateStr
  return d.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
  })
}

/** Local time: 22:00 */
export function formatTime(dateStr: string): string {
  const d = parseApiDate(dateStr)
  if (Number.isNaN(d.getTime())) return dateStr
  return d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

/** Short local date for lists: 2026-07-09 */
export function formatDateShort(dateStr: string): string {
  const d = parseApiDate(dateStr)
  if (Number.isNaN(d.getTime())) return dateStr.slice(0, 10)
  return d.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

/** W/D/L or win/draw/loss → 胜/平/负 */
export function resultToZh(code?: string | null): string {
  if (!code) return '—'
  const c = String(code).trim().toUpperCase()
  if (c === 'W' || c === 'WIN' || c === 'HOME') return '胜'
  if (c === 'D' || c === 'DRAW') return '平'
  if (c === 'L' || c === 'LOSS' || c === 'AWAY') return '负'
  if (c === '胜' || c === '平' || c === '负') return c
  return code
}

export function resultTagType(
  code?: string | null,
): 'success' | 'warning' | 'error' | 'default' {
  const zh = resultToZh(code)
  if (zh === '胜') return 'success'
  if (zh === '平') return 'warning'
  if (zh === '负') return 'error'
  return 'default'
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

/** Format rank like commercial apps: [5] */
export function rankBracket(rank?: number | null): string {
  if (rank == null || Number.isNaN(Number(rank))) return ''
  return `[${rank}]`
}

export function formatOdd(value?: string | number | null): string {
  if (value == null || value === '') return '—'
  return String(value)
}

export function formCharClass(zh: string): string {
  if (zh === '胜') return 'w'
  if (zh === '平') return 'd'
  if (zh === '负') return 'l'
  return ''
}

export function toPercent(prob: number, digits = 0): string {
  return `${(prob * 100).toFixed(digits)}%`
}

export function confidenceType(
  confidence: string,
): 'success' | 'warning' | 'error' | 'default' {
  if (confidence === '高') return 'success'
  if (confidence === '中') return 'warning'
  if (confidence === '低') return 'error'
  return 'default'
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '未开始',
    live: '进行中',
    finished: '已结束',
    postponed: '延期',
    cancelled: '取消',
  }
  return map[status.toLowerCase()] || status
}

export function statusTagType(
  status: string,
): 'default' | 'success' | 'warning' | 'error' | 'info' {
  const key = status.toLowerCase()
  if (key === 'pending') return 'info'
  if (key === 'live') return 'warning'
  if (key === 'finished') return 'success'
  if (key === 'cancelled' || key === 'postponed') return 'error'
  return 'default'
}

export function analysisConclusion(
  recommendation: string,
  probabilities: ProbabilitiesResponse,
): string {
  const top =
    recommendation === '主胜'
      ? probabilities.home_win_prob
      : recommendation === '客胜'
        ? probabilities.away_win_prob
        : probabilities.draw_prob
  return `${recommendation}概率较高（约 ${toPercent(top)}）`
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

export function leagueTagColor(leagueId: number): string {
  return LEAGUE_COLORS[Math.abs(leagueId) % LEAGUE_COLORS.length]
}
