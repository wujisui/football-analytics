import type { CalcSelection, FoldMode } from '@/utils/betCalculator'
import { foldModeLabel } from '@/utils/betCalculator'
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

/** Legacy localStorage reader — only used for one-shot API migration. */
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

function planDayOfSelections(selections: CalcSelection[]): string {
  const days = selections
    .map((s) => {
      if (s.fixtureDate) return toScheduleDayKey(s.fixtureDate)
      return ''
    })
    .filter(Boolean)
    .sort()
  return days[0] || todayDate()
}

export function createBetPlan(input: {
  name?: string
  fold: FoldMode
  multiplier: number
  selections: CalcSelection[]
}): SavedBetPlan {
  const selections = input.selections.map((s) => ({ ...s }))
  const planDay = planDayOfSelections(selections)
  const name = (input.name || '').trim() || foldModeLabel(input.fold)
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
