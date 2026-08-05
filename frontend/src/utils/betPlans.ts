import type { CalcSelection, FoldMode } from '@/utils/betCalculator'
import { foldModeLabel, selectedFixtureIds } from '@/utils/betCalculator'
import { toScheduleDayKey } from '@/utils/format'
import { todayDate } from '@/utils/homeDateStrip'

export const BET_PLANS_STORAGE_KEY = 'fa-bet-plans'

export type SavedBetPlan = {
  id: string
  name: string
  savedAt: string
  /** Earliest selection schedule day (YYYY-MM-DD) for calendar filter. */
  planDay: string
  fold: FoldMode
  multiplier: number
  selections: CalcSelection[]
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

function isPlan(raw: unknown): raw is SavedBetPlan {
  if (!raw || typeof raw !== 'object') return false
  const p = raw as Record<string, unknown>
  return (
    typeof p.id === 'string' &&
    typeof p.name === 'string' &&
    typeof p.savedAt === 'string' &&
    typeof p.planDay === 'string' &&
    DATE_RE.test(p.planDay) &&
    typeof p.fold === 'string' &&
    typeof p.multiplier === 'number' &&
    Array.isArray(p.selections)
  )
}

export function readBetPlans(): SavedBetPlan[] {
  try {
    const raw = localStorage.getItem(BET_PLANS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isPlan)
  } catch {
    return []
  }
}

/** False when the write was rejected (quota / private mode) — caller must surface it. */
export function writeBetPlans(plans: SavedBetPlan[]): boolean {
  try {
    localStorage.setItem(BET_PLANS_STORAGE_KEY, JSON.stringify(plans))
    return true
  } catch {
    return false
  }
}

export function planDayOfSelections(selections: CalcSelection[]): string {
  const days = selections
    .map((s) => {
      if (s.fixtureDate) return toScheduleDayKey(s.fixtureDate)
      return ''
    })
    .filter(Boolean)
    .sort()
  return days[0] || todayDate()
}

/** Default name: ``08-05 3串1 · 3场``. */
export function defaultPlanName(
  selections: CalcSelection[],
  fold: FoldMode,
): string {
  const day = planDayOfSelections(selections)
  const mmdd = day.slice(5)
  const n = selectedFixtureIds(selections).length
  return `${mmdd} ${foldModeLabel(fold)} · ${n}场`
}

export function createBetPlan(input: {
  name?: string
  fold: FoldMode
  multiplier: number
  selections: CalcSelection[]
}): SavedBetPlan {
  const selections = input.selections.map((s) => ({ ...s }))
  const planDay = planDayOfSelections(selections)
  const name = (input.name || '').trim() || defaultPlanName(selections, input.fold)
  return {
    id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    name,
    savedAt: new Date().toISOString(),
    planDay,
    fold: input.fold,
    multiplier: Math.max(1, Math.floor(input.multiplier) || 1),
    selections,
  }
}

export function betPlanDays(plans: readonly SavedBetPlan[]): Set<string> {
  return new Set(plans.map((p) => p.planDay))
}
