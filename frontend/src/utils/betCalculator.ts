import type { FixtureResponse } from '@/api/types'
import { hasKickedOff, parseApiDate, toScheduleDayKey } from '@/utils/format'
import { scheduleTodayDate } from '@/utils/homeDateStrip'
import { formatSignedHandicapLine } from '@/utils/handicapDisplay'
import { ahLinesOf, oddsSnippetFromFixture } from '@/utils/oddsDisplay'

export type CalcMarket = 'spf' | 'ah' | 'ou' | 'btts'

export type CalcOutcome =
  | 'home'
  | 'draw'
  | 'away'
  | 'over'
  | 'under'
  | 'yes'
  | 'no'

export interface CalcSelection {
  fixtureId: number
  leagueId: number
  homeName: string
  awayName: string
  kickoff: string
  /** ISO kickoff from API — used for calendar day / settlement. */
  fixtureDate?: string
  leagueName: string
  market: CalcMarket
  outcome: CalcOutcome
  /** Display play name, e.g. 胜平负 / 让球 -1 / 大小 2.5 */
  playLabel: string
  /** Display pick, e.g. 胜 (1.72) */
  pickLabel: string
  odd: number
  line?: string
}

/**
 * Drop past-day / already-kicked-off picks from the live bet slip.
 * Aligns with calculator list: only pending fixtures from schedule-today onward.
 */
export function pruneExpiredCalcSelections(
  selections: CalcSelection[],
  now: Date = new Date(),
): CalcSelection[] {
  if (!selections.length) return selections
  const cutoffDay = scheduleTodayDate(now)
  const nowMs = now.getTime()
  return selections.filter((s) => {
    if (!s.fixtureDate) return false
    const day = toScheduleDayKey(s.fixtureDate)
    if (!day || day < cutoffDay) return false
    if (Number.isNaN(parseApiDate(s.fixtureDate).getTime())) return false
    return !hasKickedOff(s.fixtureDate, nowMs)
  })
}

export interface CalcCell {
  market: CalcMarket
  outcome: CalcOutcome
  displayLabel: string
  playLabel: string
  pickLabel: string
  odd: number | null
  line?: string
  disabled: boolean
  disabledReason?: string
}

export interface CalcMarketRow {
  market: CalcMarket
  title: string
  playLabel: string
  line?: string
  cells: CalcCell[]
}

const STAKE_PER_BET = 2

function parseOddNumber(value: string | number | null | undefined): number | null {
  if (value == null || value === '') return null
  const n = typeof value === 'number' ? value : Number(String(value).trim())
  return Number.isFinite(n) && n > 1 ? n : null
}

export function outcomeTitle(
  market: CalcMarket,
  outcome: CalcOutcome,
): string {
  if (market === 'spf' || market === 'ah') {
    if (outcome === 'home') return '胜'
    if (outcome === 'draw') return '平'
    if (outcome === 'away') return '负'
  }
  if (market === 'ou') {
    if (outcome === 'over') return '大'
    if (outcome === 'under') return '小'
  }
  if (market === 'btts') {
    if (outcome === 'yes') return '是'
    if (outcome === 'no') return '否'
  }
  return String(outcome)
}

/** Build selectable rows for one fixture from available odds. */
export function buildMarketRows(
  fixture: FixtureResponse,
): CalcMarketRow[] {
  const odds = oddsSnippetFromFixture(fixture)
  const rows: CalcMarketRow[] = []

  const mw = odds?.match_winner
  rows.push({
    market: 'spf',
    title: '全场独赢',
    playLabel: '胜平负',
    cells: [
      cell('spf', 'home', '主胜', '胜平负', parseOddNumber(mw?.home)),
      cell('spf', 'draw', '和局', '胜平负', parseOddNumber(mw?.draw)),
      cell('spf', 'away', '客胜', '胜平负', parseOddNumber(mw?.away)),
    ],
  })

  const ah = ahLinesOf(odds?.asian_handicap)[0]
  const ahLine = ah?.line != null ? String(ah.line) : undefined
  const shownAhLine = effectiveHandicapLine(ahLine)
  const ahPlay = shownAhLine ? `让球 ${shownAhLine}` : '让球'
  rows.push({
    market: 'ah',
    title: '全场让球',
    playLabel: ahPlay,
    line: ahLine,
    cells: [
      cell(
        'ah',
        'home',
        shownAhLine ?? '主队',
        ahPlay,
        parseOddNumber(ah?.home),
        ahLine,
      ),
      cell(
        'ah',
        'away',
        oppositeHandicapLine(ahLine) ?? '客队',
        ahPlay,
        parseOddNumber(ah?.away),
        ahLine,
      ),
    ],
  })

  const ou = odds?.goals_ou
  const ouLine = ou?.line != null ? String(ou.line) : undefined
  const ouPlay = ouLine ? `大小 ${ouLine}` : '大小球'
  const btts = odds?.both_teams_score
  const ouCells = [
    cell('ou', 'over', `大${ouLine ?? ''}`, ouPlay, parseOddNumber(ou?.home), ouLine),
    cell('ou', 'under', `小${ouLine ?? ''}`, ouPlay, parseOddNumber(ou?.away), ouLine),
  ]
  const bttsCells = [
    cell('btts', 'yes', '是', '双进', parseOddNumber(btts?.home)),
    cell('btts', 'no', '否', '双进', parseOddNumber(btts?.away)),
  ]
  rows.push({
    market: 'ou',
    title: '全场大小',
    playLabel: ouLine ? `大小 ${ouLine}` : '大小',
    line: ouLine,
    cells: ouCells,
  })
  rows.push({
    market: 'btts',
    title: '全场双进',
    playLabel: '双进',
    cells: bttsCells,
  })

  return rows
}

function cell(
  market: CalcMarket,
  outcome: CalcOutcome,
  displayLabel: string,
  playLabel: string,
  odd: number | null,
  line?: string,
  disabledReason?: string,
): CalcCell {
  const disabled = odd == null
  return {
    market,
    outcome,
    displayLabel,
    playLabel,
    pickLabel: `${outcomeTitle(market, outcome)}${odd != null ? ` (${odd})` : ''}`,
    odd,
    line,
    disabled,
    disabledReason: disabled ? disabledReason || '暂无赔率' : undefined,
  }
}

function oppositeHandicapLine(line: string | null | undefined): string | undefined {
  if (line == null || line === '') return undefined
  const n = Number(String(line).replace(',', '.').trim())
  if (!Number.isFinite(n)) return String(line)
  return formatSignedHandicapLine(-n)
}

/** Signed line text for the book line that actually settles the pick. */
export function effectiveHandicapLine(
  line: string | null | undefined,
): string | undefined {
  if (line == null || line === '') return undefined
  const n = Number(String(line).replace(',', '.').trim())
  if (!Number.isFinite(n)) return String(line)
  return formatSignedHandicapLine(n)
}

export function selectedFixtureIds(selections: CalcSelection[]): number[] {
  return [...new Set(selections.map((s) => s.fixtureId))]
}

export type FoldMode = `${number}x1`

export function availableFoldModes(matchCount: number): FoldMode[] {
  if (matchCount <= 0) return []
  if (matchCount === 1) return ['1x1']
  const modes: FoldMode[] = []
  for (let k = 2; k <= matchCount; k += 1) {
    modes.push(`${k}x1` as FoldMode)
  }
  return modes
}

export function foldModeLabel(mode: FoldMode): string {
  const [n] = mode.split('x')
  if (n === '1') return '单关'
  return `${n}串1`
}

export interface ParlayCombo {
  fixtureIds: number[]
  oddsProduct: number
  prize: number
  picks: CalcSelection[]
}

export interface ParlayResult {
  fold: FoldMode
  matchCount: number
  betCount: number
  multiplier: number
  stakeYuan: number
  /** Sum of combo prizes. */
  estimatedPrize: number
  combos: ParlayCombo[]
}

/**
 * 串关：对已选场次按 M串1 枚举 C(N,M)，
 * 历史方案可能含同场多选项，结算时继续按笛卡尔积拆注。
 */
export function calculateParlay(
  selections: CalcSelection[],
  fold: FoldMode,
  multiplier: number,
): ParlayResult {
  const byFixture = new Map<number, CalcSelection[]>()
  for (const sel of selections) {
    const list = byFixture.get(sel.fixtureId) ?? []
    list.push(sel)
    byFixture.set(sel.fixtureId, list)
  }
  const fixtureIds = [...byFixture.keys()]
  const matchCount = fixtureIds.length
  const m = Number(fold.split('x')[0]) || 0
  const mult = Math.max(1, Math.floor(multiplier) || 1)

  if (matchCount === 0 || m < 1 || m > matchCount) {
    return {
      fold,
      matchCount,
      betCount: 0,
      multiplier: mult,
      stakeYuan: 0,
      estimatedPrize: 0,
      combos: [],
    }
  }

  const groups = combinations(fixtureIds, m)
  const combos: ParlayCombo[] = []
  for (const ids of groups) {
    const optionSets = ids.map((id) => byFixture.get(id) ?? [])
    for (const picks of cartesian(optionSets)) {
      const oddsProduct = picks.reduce((acc, s) => acc * s.odd, 1)
      const prize = round2(oddsProduct * STAKE_PER_BET * mult)
      combos.push({
        fixtureIds: ids,
        oddsProduct: round2(oddsProduct),
        prize,
        picks,
      })
    }
  }

  const betCount = combos.length
  const estimatedPrize = round2(combos.reduce((s, c) => s + c.prize, 0))

  return {
    fold,
    matchCount,
    betCount,
    multiplier: mult,
    stakeYuan: betCount * STAKE_PER_BET * mult,
    estimatedPrize,
    combos,
  }
}

function combinations<T>(arr: T[], k: number): T[][] {
  if (k <= 0 || k > arr.length) return []
  if (k === arr.length) return [arr.slice()]
  if (k === 1) return arr.map((x) => [x])
  const out: T[][] = []
  const walk = (start: number, path: T[]) => {
    if (path.length === k) {
      out.push(path.slice())
      return
    }
    for (let i = start; i < arr.length; i += 1) {
      path.push(arr[i])
      walk(i + 1, path)
      path.pop()
    }
  }
  walk(0, [])
  return out
}

function cartesian<T>(arrays: T[][]): T[][] {
  if (!arrays.length) return [[]]
  return arrays.reduce<T[][]>(
    (acc, arr) => {
      if (!arr.length) return []
      return acc.flatMap((prefix) => arr.map((item) => [...prefix, item]))
    },
    [[]],
  )
}

function round2(n: number): number {
  return Math.round(n * 100) / 100
}

export const MAX_CALC_MATCHES = 10
export { STAKE_PER_BET }
