import { computed, ref } from 'vue'

import {
  createBetPlan as apiCreate,
  deleteBetPlan as apiDelete,
  fetchBetPlanDays,
  fetchBetPlans,
  renameBetPlan as apiRename,
  type BetPlanDto,
} from '@/api/betPlans'
import type { CalcSelection, FoldMode } from '@/utils/betCalculator'
import {
  BET_PLANS_STORAGE_KEY,
  createBetPlan as buildLocalPlan,
  readBetPlans,
  type SavedBetPlan,
} from '@/utils/betPlans'

const plans = ref<SavedBetPlan[]>([])
const loaded = ref(false)
const MIGRATED_KEY = 'fa-bet-plans-migrated-v1'

function dtoToPlan(row: BetPlanDto): SavedBetPlan {
  return {
    id: row.id,
    name: row.name,
    savedAt: row.saved_at,
    planDay: row.plan_day,
    fold: row.fold as FoldMode,
    multiplier: row.multiplier,
    selections: row.selections as CalcSelection[],
  }
}

/** One-shot: push legacy localStorage plans into the API owner bucket. */
async function migrateLocalPlansIfNeeded() {
  try {
    if (localStorage.getItem(MIGRATED_KEY) === '1') return
    const legacy = readBetPlans()
    if (!legacy.length) {
      localStorage.setItem(MIGRATED_KEY, '1')
      return
    }
    for (const plan of legacy) {
      try {
        await apiCreate({
          id: plan.id,
          name: plan.name,
          plan_day: plan.planDay,
          fold: plan.fold,
          multiplier: plan.multiplier,
          selections: plan.selections,
        })
      } catch {
        /* duplicate id or validation — skip */
      }
    }
    localStorage.removeItem(BET_PLANS_STORAGE_KEY)
    localStorage.setItem(MIGRATED_KEY, '1')
  } catch {
    /* private mode */
  }
}

export function useBetPlans() {
  const planDays = computed(() => new Set(plans.value.map((p) => p.planDay)))

  async function reload() {
    await migrateLocalPlansIfNeeded()
    const data = await fetchBetPlans()
    plans.value = data.plans.map(dtoToPlan)
    loaded.value = true
  }

  async function savePlan(input: {
    name?: string
    fold: FoldMode
    multiplier: number
    selections: CalcSelection[]
  }): Promise<SavedBetPlan | null> {
    const draft = buildLocalPlan(input)
    try {
      const row = await apiCreate({
        name: draft.name,
        plan_day: draft.planDay,
        fold: draft.fold,
        multiplier: draft.multiplier,
        selections: draft.selections,
      })
      const plan = dtoToPlan(row)
      plans.value = [plan, ...plans.value.filter((p) => p.id !== plan.id)]
      return plan
    } catch {
      return null
    }
  }

  async function renamePlan(id: string, name: string): Promise<boolean> {
    const next = name.trim()
    if (!next) return false
    try {
      const row = await apiRename(id, next)
      const plan = dtoToPlan(row)
      plans.value = plans.value.map((p) => (p.id === id ? plan : p))
      return true
    } catch {
      return false
    }
  }

  async function removePlan(id: string) {
    await apiDelete(id)
    plans.value = plans.value.filter((p) => p.id !== id)
  }

  function getPlan(id: string): SavedBetPlan | null {
    return plans.value.find((p) => p.id === id) ?? null
  }

  function plansForDay(day: string): SavedBetPlan[] {
    return plans.value
      .filter((p) => p.planDay === day)
      .sort((a, b) => b.savedAt.localeCompare(a.savedAt))
  }

  async function loadDays(): Promise<Set<string>> {
    const days = await fetchBetPlanDays()
    return new Set(days)
  }

  return {
    plans,
    planDays,
    loaded,
    reload,
    savePlan,
    renamePlan,
    removePlan,
    getPlan,
    plansForDay,
    loadDays,
  }
}
