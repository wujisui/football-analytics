import type { FixtureResponse, LineOdds } from '@/api/types'
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

export interface CalcCell {
  market: CalcMarket
  outcome: CalcOutcome
  playLabel: string
  pickLabel: string
  odd: number | null
  line?: string
  disabled: boolean
  disabledReason?: string
}

export interface CalcMarketRow {
  market: CalcMarket
  playLabel: string
  line?: string
  cells: CalcCell[]
}

const STAKE_PER_BET = 2
/** 胜平负最多双选 */
export const MAX_SPF_PICKS = 2

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

function isIntegerHandicapLine(line?: string | null): boolean {
  if (line == null || line === '') return false
  const n = Number(String(line).replace(',', '.').trim())
  return Number.isFinite(n) && Math.abs(n - Math.round(n)) < 1e-9
}

/** Build selectable rows for one fixture from available odds. */
export function buildMarketRows(fixture: FixtureResponse): CalcMarketRow[] {
  const odds = oddsSnippetFromFixture(fixture)
  const rows: CalcMarketRow[] = []

  const mw = odds?.match_winner
  rows.push({
    market: 'spf',
    playLabel: '胜平负',
    cells: [
      cell('spf', 'home', '胜平负', parseOddNumber(mw?.home)),
      cell('spf', 'draw', '胜平负', parseOddNumber(mw?.draw)),
      cell('spf', 'away', '胜平负', parseOddNumber(mw?.away)),
    ],
  })

  const ahMarket = odds?.asian_handicap
  const ah = ahLinesOf(ahMarket)[0]
  const ahLine = ah?.line != null ? String(ah.line) : undefined
  const ahPlay = ahLine ? `让球 ${formatSignedLine(ahLine)}` : '让球胜平负'
  const ahDraw = resolveAhDrawOdd(ahMarket, ahLine, parseOddNumber(ah?.home), parseOddNumber(ah?.away))
  rows.push({
    market: 'ah',
    playLabel: ahPlay,
    line: ahLine,
    cells: [
      cell('ah', 'home', ahPlay, parseOddNumber(ah?.home), ahLine),
      cell(
        'ah',
        'draw',
        ahPlay,
        ahDraw,
        ahLine,
        ahDraw == null
          ? isIntegerHandicapLine(ahLine)
            ? '暂无让平赔率'
            : '非整数盘口无让平'
          : undefined,
      ),
      cell('ah', 'away', ahPlay, parseOddNumber(ah?.away), ahLine),
    ],
  })

  const ou = odds?.goals_ou
  const ouLine = ou?.line != null ? String(ou.line) : undefined
  const ouPlay = ouLine ? `大小 ${ouLine}` : '大小球'
  const btts = odds?.both_teams_score
  rows.push({
    market: 'ou',
    playLabel: '大小/双进',
    line: ouLine,
    cells: [
      cell('ou', 'over', ouPlay, parseOddNumber(ou?.home), ouLine),
      cell('ou', 'under', ouPlay, parseOddNumber(ou?.away), ouLine),
      cell('btts', 'yes', '双进', parseOddNumber(btts?.home)),
      cell('btts', 'no', '双进', parseOddNumber(btts?.away)),
    ],
  })

  return rows
}

function resolveAhDrawOdd(
  market: LineOdds | null | undefined,
  line: string | undefined,
  homeOdd: number | null,
  awayOdd: number | null,
): number | null {
  const fromValues = parseAhDrawFromValues(market, line)
  if (fromValues != null) return fromValues
  // 整数盘口下亚洲盘为两路，竞彩「让平」可估一个参考赔供计算器使用
  if (!isIntegerHandicapLine(line) || homeOdd == null || awayOdd == null) return null
  return round2(Math.max(2.2, (homeOdd + awayOdd) * 0.95))
}

function parseAhDrawFromValues(
  market: LineOdds | null | undefined,
  line: string | undefined,
): number | null {
  const values = market?.values
  if (!values?.length) return null
  const lineNorm = line != null ? normalizeLineToken(line) : null
  for (const v of values) {
    const label = String(v.label || '').trim().toLowerCase()
    if (!label) continue
    const isDraw =
      label === 'draw'
      || label === 'x'
      || label.startsWith('draw ')
      || label.includes(' draw')
      || /\bdraw\b/.test(label)
    if (!isDraw) continue
    if (lineNorm != null) {
      const token = extractLineFromLabel(label)
      if (token != null && normalizeLineToken(token) !== lineNorm) continue
    }
    const odd = parseOddNumber(v.odd)
    if (odd != null) return odd
  }
  return null
}

function extractLineFromLabel(label: string): string | null {
  const m = label.match(/([+-]?\d+(?:[.,]\d+)?)/)
  return m ? m[1].replace(',', '.') : null
}

function normalizeLineToken(line: string): string {
  const n = Number(String(line).replace(',', '.').trim())
  if (!Number.isFinite(n)) return String(line).trim()
  return String(n)
}

function cell(
  market: CalcMarket,
  outcome: CalcOutcome,
  playLabel: string,
  odd: number | null,
  line?: string,
  disabledReason?: string,
): CalcCell {
  const disabled = odd == null
  return {
    market,
    outcome,
    playLabel,
    pickLabel: `${outcomeTitle(market, outcome)}${odd != null ? ` (${odd})` : ''}`,
    odd,
    line,
    disabled,
    disabledReason: disabled ? disabledReason || '暂无赔率' : undefined,
  }
}

function formatSignedLine(line: string): string {
  const n = Number(line)
  if (!Number.isFinite(n)) return line
  if (n > 0) return `+${n}`
  return String(n)
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
  /** Sum of combo prizes (dual-select expands bet count). */
  estimatedPrize: number
  combos: ParlayCombo[]
}

/**
 * 竞彩风格：对已选场次按 M串1 枚举 C(N,M)，
 * 同场多选项（如胜平负双选）再做笛卡尔积拆注。
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
