import {
  calculateParlay,
  STAKE_PER_BET,
  type CalcOutcome,
  type CalcSelection,
  type FoldMode,
  type ParlayCombo,
} from '@/utils/betCalculator'

export type FixtureScoreSnap = {
  fixture_id: number
  status: string
  home_goals?: number | null
  away_goals?: number | null
}

/** hit | miss | void(走水作废) | pending(未完场/无比分) */
export type LegVerdict = 'hit' | 'miss' | 'void' | 'pending'

export type SettledLeg = {
  pick: CalcSelection
  verdict: LegVerdict
  scoreText: string | null
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

function parseLine(line?: string): number | null {
  if (line == null || line === '') return null
  const n = Number(String(line).replace(',', '.').trim())
  return Number.isFinite(n) ? n : null
}

function settleAhLabel(
  home: number,
  away: number,
  line: number,
): 'cover' | 'no_cover' | 'push' {
  const margin = home + line - away
  if (Math.abs(margin) < 1e-9) return 'push'
  return margin > 0 ? 'cover' : 'no_cover'
}

export function settleSelection(
  pick: CalcSelection,
  snap: FixtureScoreSnap | undefined,
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
    const line = parseLine(pick.line)
    if (line == null) return { verdict: 'pending', scoreText }
    const label = settleAhLabel(h, a, line)
    if (pick.outcome === 'home') {
      return { verdict: label === 'cover' ? 'hit' : 'miss', scoreText }
    }
    if (pick.outcome === 'away') {
      return { verdict: label === 'no_cover' ? 'hit' : 'miss', scoreText }
    }
    if (pick.outcome === 'draw') {
      return { verdict: label === 'push' ? 'hit' : 'miss', scoreText }
    }
    return { verdict: 'miss', scoreText }
  }

  if (pick.market === 'ou') {
    const line = parseLine(pick.line)
    if (line == null) return { verdict: 'pending', scoreText }
    const total = h + a
    // Integer line exact total → void (option B).
    if (Math.abs(total - line) < 1e-9) {
      return { verdict: 'void', scoreText }
    }
    const over = total > line
    if (pick.outcome === 'over') {
      return { verdict: over ? 'hit' : 'miss', scoreText }
    }
    if (pick.outcome === 'under') {
      return { verdict: over ? 'miss' : 'hit', scoreText }
    }
    return { verdict: 'miss', scoreText }
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

  // Void legs pass through as odd=1; all-void → refund stake for this bet.
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

  const oddsProduct = round2(active.reduce((acc, s) => acc * s.odd, 1))
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
): PlanSettlement {
  const parlay = calculateParlay(selections, fold, multiplier)
  const legs: SettledLeg[] = selections.map((pick) => {
    const { verdict, scoreText } = settleSelection(pick, scores.get(pick.fixtureId))
    return { pick, verdict, scoreText }
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
