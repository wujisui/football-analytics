import { ref } from 'vue'

import {
  fetchLeagueFilterOptions,
  type LeagueFilterOption,
  type LeagueFilterOptionsResponse,
} from '@/api/leagues'
import { resolveTrackedSelection } from '@/utils/leagueFilterSelection'

// v4: prematch options cover backend-local today + tomorrow, not one UTC day.
// v5: v4 也存了加载时推导的勾选，赛程未同步全时会落下残缺集合并压过默认热门。
// v5 只存用户确认过的选择，旧键直接作废。
const STORAGE_KEY = 'fa-tracked-league-ids-by-date-v5'

const filterOptions = ref<LeagueFilterOptionsResponse | null>(null)
const trackedIds = ref<number[]>([])
const filterOptionsError = ref('')
let activeFilterDate = ''
/** Last loaded scope — avoid mixing prematch/results checklist caches. */
let activeFilterScope: 'prematch' | 'results' = 'prematch'

let inflightFilterOptions: Promise<LeagueFilterOptionsResponse> | null = null
let inflightFilterOptionsKey = ''
let filterLoadSeq = 0

/** Prematch filter frozen while 赛程 future-day overrides shared options. */
let frozenPrematch: {
  filterOptions: LeagueFilterOptionsResponse | null
  trackedIds: number[]
  activeFilterDate: string
  activeFilterScope: 'prematch' | 'results'
} | null = null

function readStoredIds(date: string): number[] | null {
  if (!date) return null
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
    const ids = (parsed as Record<string, unknown>)[date]
    if (!Array.isArray(ids)) return null
    return ids.map(Number).filter((n) => Number.isFinite(n))
  } catch {
    return null
  }
}

function persistTracked(ids: number[], date: string) {
  if (!date) return
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    const byDate =
      parsed && typeof parsed === 'object' && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : {}
    byDate[date] = ids
    localStorage.setItem(STORAGE_KEY, JSON.stringify(byDate))
  } catch {
    /* ignore */
  }
}

/** Derived selection (filter-options 重算)：只更新内存，不当成用户选择落库。 */
function setTrackedIds(ids: number[]) {
  trackedIds.value = [
    ...new Set(ids.map(Number).filter((n) => Number.isFinite(n))),
  ]
}

/** 用户在筛选弹窗点了确认：这才是可以覆盖默认热门的显式选择。 */
function commitTrackedIds(ids: number[]) {
  setTrackedIds(ids)
  persistTracked(trackedIds.value, activeFilterDate)
}

function allFilterOptions(): LeagueFilterOption[] {
  const data = filterOptions.value
  if (!data) return []
  return [...data.configured, ...data.extra]
}

function syncTrackedWithFilterOptions() {
  const options = allFilterOptions()
  if (!options.length) {
    trackedIds.value = []
    return
  }
  setTrackedIds(
    resolveTrackedSelection(options, readStoredIds(activeFilterDate) ?? []),
  )
}

/**
 * Before 赛程 loads filter-options for a future day: keep calculator selection so
 * returning home can restore instantly (no flash of future-day leagues).
 */
export function beginScheduleFilterOverride(): void {
  if (frozenPrematch) return
  frozenPrematch = {
    filterOptions: filterOptions.value,
    trackedIds: [...trackedIds.value],
    activeFilterDate,
    activeFilterScope,
  }
}

/** Restore calculator filter after leaving future schedule. */
export function endScheduleFilterOverride(): void {
  if (!frozenPrematch) return
  filterOptions.value = frozenPrematch.filterOptions
  trackedIds.value = frozenPrematch.trackedIds
  activeFilterDate = frozenPrematch.activeFilterDate
  activeFilterScope = frozenPrematch.activeFilterScope
  frozenPrematch = null
}

async function loadFilterOptions(options?: {
  date?: string
  days?: number
  scope?: 'prematch' | 'results'
}): Promise<LeagueFilterOptionsResponse> {
  const scope = options?.scope ?? 'prematch'
  const key = `${options?.date ?? ''}|${options?.days ?? ''}|${scope}`
  if (inflightFilterOptions && inflightFilterOptionsKey === key) {
    return inflightFilterOptions
  }

  const seq = ++filterLoadSeq
  filterOptionsError.value = ''
  inflightFilterOptionsKey = key
  inflightFilterOptions = (async () => {
    try {
      const data = await fetchLeagueFilterOptions({
        date: options?.date,
        days: options?.days,
        scope,
      })
      if (seq !== filterLoadSeq) return data
      filterOptions.value = data
      activeFilterDate = data.date
      activeFilterScope = scope
      syncTrackedWithFilterOptions()
      return data
    } catch (err) {
      if (seq === filterLoadSeq) {
        filterOptionsError.value =
          err instanceof Error ? err.message : '加载联赛筛选选项失败'
      }
      throw err
    } finally {
      if (seq === filterLoadSeq) {
        inflightFilterOptions = null
        inflightFilterOptionsKey = ''
      }
    }
  })()

  return inflightFilterOptions
}

export function useTrackedLeagues() {
  return {
    filterOptions,
    trackedIds,
    filterOptionsError,
    commitTrackedIds,
    allFilterOptions,
    loadFilterOptions,
  }
}
