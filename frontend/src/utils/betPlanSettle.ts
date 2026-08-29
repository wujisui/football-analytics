import {
  calculateParlay,
  STAKE_PER_BET,
  type CalcOutcome,
  type CalcSelection,
  type FoldMode,
  type ParlayCombo,
} from '@/utils/betCalculator'
import { parseApiDate } from '@/utils/format'
import { jcHandicapLine, type HandicapRuleset } from '@/utils/handicapRuleset'

export type FixtureScoreSnap = {
  fixture_id: number
  status: string
  /** Current ISO kickoff — differs from the frozen pick when officially rescheduled. */
  fixture_date?: string
  home_goals?: number | null
  away_goals?: number | null
}

/** Full/partial Asian settlement plus void and pending. */
export type LegVerdict =
  | 'hit'
  | 'half_win'
  | 'half_loss'
  | 'miss'
  | 'void'
  | 'pending'

export type SettledLeg = {
  pick: CalcSelection
  verdict: LegVerdict
  scoreText: string | null
  /** ISO kickoff the fixture was moved to, when it no longer matches the saved pick. */
  rescheduledTo: string | null
}

export type SettledCombo = {
  picks: CalcSelection[]
  /** Odds after treating void legs as 1.0 */
  oddsProduct: number
  estimatedPrize: number
  actualPrize: number
  /** lost if any miss; void if all remaining void/empty; won if all hit/void with ≥1 hit path */
  status: 'won' | 'lost' | 'void' | 'pending'
  legVerdicts: LegVerdict[]
}

export type PlanSettlement = {
  legs: SettledLeg[]
  combos: SettledCombo[]
  stakeYuan: number
  estimatedPrize: number
  actualPrize: number
  /**
   * Aggregate by betting rules:
   * - won if any combo won
   * - pending only if some combo still can win (no miss yet)
   * - void if all void; else lost
   */
  status: 'pending' | 'won' | 'lost' | 'void'
}

function isFinishedStatus(status: string): boolean {
  const s = status.toLowerCase()
  return s === 'finished' || s === 'ft' || s === 'aet' || s === 'pen'
}

function isCancelledStatus(status: string): boolean {
  const s = status.toLowerCase()
  return (
    s === 'cancelled' ||
    s === 'canceled' ||
    s === 'postponed' ||
    s === 'abandoned' ||
    s === 'suspended'
  )
}

/**
 * Official kickoff nudges of a few minutes are noise; a real reschedule (e.g. a
 * postponed first leg pushing the return leg a week later) moves it far more.
 */
const RESCHEDULE_TOLERANCE_MS = 30 * 60 * 1000

/**
 * Saved plans freeze the kickoff label, while settlement reads the fixture live by
 * id. When the official schedule moves a fixture the two disagree and the leg would
 * otherwise sit on 待定 with no explanation.
 */
export function rescheduledKickoff(
  pick: CalcSelection,
  snap: FixtureScoreSnap | undefined,
): string | null {
  if (!snap?.fixture_date || !pick.fixtureDate) return null
  const current = parseApiDate(snap.fixture_date).getTime()
  const saved = parseApiDate(pick.fixtureDate).getTime()
  if (Number.isNaN(current) || Number.isNaN(saved)) return null
  if (Math.abs(current - saved) < RESCHEDULE_TOLERANCE_MS) return null
  return snap.fixture_date
}

function parseLine(line?: string): number | null {
  if (line == null || line === '') return null
  const n = Number(String(line).replace(',', '.').trim())
  return Number.isFinite(n) ? n : null
}

function splitQuarterLine(line: number): number[] {
  const quarters = Math.round(line * 4)
  if (Math.abs(line * 4 - quarters) > 1e-7 || quarters % 2 === 0) return [line]
  return [(quarters - 1) / 4, (quarters + 1) / 4]
}

function combineSplitResults(parts: number[]): LegVerdict {
  if (parts.every((part) => part > 0)) return 'hit'
  if (parts.some((part) => part > 0) && parts.some((part) => part === 0)) {
    return 'half_win'
  }
  if (parts.every((part) => part === 0)) return 'void'
  if (parts.some((part) => part < 0) && parts.some((part) => part === 0)) {
    return 'half_loss'
  }
  return 'miss'
}

function splitMarginVerdict(
  line: number,
  marginForLine: (splitLine: number) => number,
): LegVerdict {
  const parts = splitQuarterLine(line).map((splitLine) => {
    const margin = marginForLine(splitLine)
    return Math.abs(margin) < 1e-9 ? 0 : margin > 0 ? 1 : -1
  })
  return combineSplitResults(parts)
}

export function settleSelection(
  pick: CalcSelection,
  snap: FixtureScoreSnap | undefined,
  ruleset: HandicapRuleset = 'asian',
): { verdict: LegVerdict; scoreText: string | null } {
  if (!snap) return { verdict: 'pending', scoreText: null }
  if (isCancelledStatus(snap.status)) {
    return { verdict: 'void', scoreText: null }
  }
  const h = snap.home_goals
  const a = snap.away_goals
  if (
    !isFinishedStatus(snap.status) ||
    h == null ||
    a == null ||
    !Number.isFinite(h) ||
    !Number.isFinite(a)
  ) {
    return { verdict: 'pending', scoreText: null }
  }
  const scoreText = `${h}:${a}`

  if (pick.market === 'spf') {
    let actual: CalcOutcome = 'draw'
    if (h > a) actual = 'home'
    else if (h < a) actual = 'away'
    return {
      verdict: pick.outcome === actual ? 'hit' : 'miss',
      scoreText,
    }
  }

  if (pick.market === 'ah') {
    const rawLine = parseLine(pick.line)
    if (rawLine == null) return { verdict: 'pending', scoreText }
    if (ruleset === 'jc') {
      // 竞彩先把盘口向上取整，再判三项；没有赢半 / 输半。
      const line = jcHandicapLine(rawLine)
      const margin = h + line - a
      if (Math.abs(margin) < 1e-9) {
        if (Math.abs(line) < 1e-9) return { verdict: 'void', scoreText }
        return {
          verdict: pick.outcome === 'draw' ? 'hit' : 'miss',
          scoreText,
        }
      }
      return {
        verdict:
          pick.outcome === (margin > 0 ? 'home' : 'away') ? 'hit' : 'miss',
        scoreText,
      }
    }
    const line = rawLine
    const margin = h + line - a
    const integerLine = Math.abs(line - Math.round(line)) < 1e-9
    if (integerLine) {
      if (Math.abs(margin) < 1e-9) return { verdict: 'void', scoreText }
      return {
        verdict:
          pick.outcome === (margin > 0 ? 'home' : 'away') ? 'hit' : 'miss',
        scoreText,
      }
    }
    if (pick.outcome === 'draw') return { verdict: 'miss', scoreText }
    return {
      verdict: splitMarginVerdict(line, (splitLine) => {
        const homeMargin = h + splitLine - a
        return pick.outcome === 'home' ? homeMargin : -homeMargin
      }),
      scoreText,
    }
  }

  if (pick.market === 'ou') {
    const line = parseLine(pick.line)
    if (line == null) return { verdict: 'pending', scoreText }
    const total = h + a
    if (pick.outcome !== 'over' && pick.outcome !== 'under') {
      return { verdict: 'miss', scoreText }
    }
    return {
      verdict: splitMarginVerdict(line, (splitLine) => {
        const overMargin = total - splitLine
        return pick.outcome === 'over' ? overMargin : -overMargin
      }),
      scoreText,
    }
  }

  if (pick.market === 'btts') {
    const yes = h > 0 && a > 0
    if (pick.outcome === 'yes') {
      return { verdict: yes ? 'hit' : 'miss', scoreText }
    }
    if (pick.outcome === 'no') {
      return { verdict: yes ? 'miss' : 'hit', scoreText }
    }
  }

  return { verdict: 'miss', scoreText }
}

function settleCombo(
  combo: ParlayCombo,
  verdictByKey: Map<string, LegVerdict>,
  multiplier: number,
): SettledCombo {
  const legVerdicts = combo.picks.map((p) => {
    const key = `${p.fixtureId}|${p.market}|${p.outcome}`
    return verdictByKey.get(key) ?? 'pending'
  })

  // 任一腿未中 → 该注已死，不必等其余场次完场
  if (legVerdicts.some((v) => v === 'miss')) {
    return {
      picks: combo.picks,
      oddsProduct: combo.oddsProduct,
      estimatedPrize: combo.prize,
      actualPrize: 0,
      status: 'lost',
      legVerdicts,
    }
  }
  if (legVerdicts.some((v) => v === 'pending')) {
    return {
      picks: combo.picks,
      oddsProduct: combo.oddsProduct,
      estimatedPrize: combo.prize,
      actualPrize: 0,
      status: 'pending',
      legVerdicts,
    }
  }

  // Void legs pass through as 1. Half outcomes use their exact split-stake return:
  // half win=(odd+1)/2; half loss=0.5.
  const active = combo.picks.filter((_, i) => legVerdicts[i] !== 'void')
  if (!active.length) {
    return {
      picks: combo.picks,
      oddsProduct: 1,
      estimatedPrize: combo.prize,
      actualPrize: round2(STAKE_PER_BET * multiplier),
      status: 'void',
      legVerdicts,
    }
  }

  const returnFactor = (pick: CalcSelection, verdict: LegVerdict): number => {
    if (verdict === 'half_win') return (pick.odd + 1) / 2
    if (verdict === 'half_loss') return 0.5
    if (verdict === 'void') return 1
    return pick.odd
  }
  const oddsProduct = round2(
    combo.picks.reduce(
      (acc, pick, i) => acc * returnFactor(pick, legVerdicts[i]),
      1,
    ),
  )
  const actualPrize = round2(oddsProduct * STAKE_PER_BET * multiplier)
  return {
    picks: combo.picks,
    oddsProduct,
    estimatedPrize: combo.prize,
    actualPrize,
    status: 'won',
    legVerdicts,
  }
}

export function settleBetPlan(
  selections: CalcSelection[],
  fold: FoldMode,
  multiplier: number,
  scores: ReadonlyMap<number, FixtureScoreSnap>,
  ruleset: HandicapRuleset = 'asian',
): PlanSettlement {
  const parlay = calculateParlay(selections, fold, multiplier)
  const legs: SettledLeg[] = selections.map((pick) => {
    const snap = scores.get(pick.fixtureId)
    const { verdict, scoreText } = settleSelection(pick, snap, ruleset)
    return {
      pick,
      verdict,
      scoreText,
      rescheduledTo: rescheduledKickoff(pick, snap),
    }
  })

  const verdictByKey = new Map<string, LegVerdict>()
  for (const leg of legs) {
    verdictByKey.set(
      `${leg.pick.fixtureId}|${leg.pick.market}|${leg.pick.outcome}`,
      leg.verdict,
    )
  }

  const combos = parlay.combos.map((c) =>
    settleCombo(c, verdictByKey, multiplier),
  )

  let status: PlanSettlement['status']
  if (!combos.length) {
    status = legs.some((l) => l.verdict === 'pending') ? 'pending' : 'void'
  } else if (combos.some((c) => c.status === 'won')) {
    status = 'won'
  } else if (combos.some((c) => c.status === 'pending')) {
    // 仍有注单可能中奖（例如 M 串 1 多注里尚未出现未中的组合）
    status = 'pending'
  } else if (combos.every((c) => c.status === 'void')) {
    status = 'void'
  } else {
    status = 'lost'
  }

  const actualPrize = round2(
    combos.reduce((sum, c) => sum + (c.status === 'won' || c.status === 'void' ? c.actualPrize : 0), 0),
  )

  return {
    legs,
    combos,
    stakeYuan: parlay.stakeYuan,
    estimatedPrize: parlay.estimatedPrize,
    actualPrize,
    status,
  }
}

function round2(n: number): number {
  return Math.round(n * 100) / 100
}

export function planStatusLabel(status: PlanSettlement['status']): string {
  if (status === 'pending') return '待结算'
  if (status === 'won') return '已中'
  if (status === 'void') return '走水/作废'
  return '未中'
}

export function planStatusTagType(
  status: PlanSettlement['status'],
): 'error' | 'warning' | 'default' {
  if (status === 'won') return 'error'
  if (status === 'lost') return 'default'
  if (status === 'void') return 'warning'
  return 'default'
}

export type PlanWinCounts = {
  won: number
  settled: number
  total: number
}

export function summarizePlanStatuses(
  statuses: readonly PlanSettlement['status'][],
): PlanWinCounts {
  let won = 0
  let settled = 0
  for (const status of statuses) {
    if (status !== 'pending') settled += 1
    if (status === 'won') won += 1
  }
  return { won, settled, total: statuses.length }
}
