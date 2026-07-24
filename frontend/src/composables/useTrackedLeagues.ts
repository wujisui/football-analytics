import { ref } from 'vue'

import {
  fetchLeagueFilterOptions,
  type LeagueFilterOption,
  type LeagueFilterOptionsResponse,
} from '@/api/leagues'
import { resolveTrackedSelection } from '@/utils/leagueFilterSelection'

const STORAGE_KEY = 'fa-tracked-league-ids-by-date-v3'

const filterOptions = ref<LeagueFilterOptionsResponse | null>(null)
const trackedIds = ref<number[]>([])
const filterOptionsError = ref('')
let activeFilterDate = ''

let inflightFilterOptions: Promise<LeagueFilterOptionsResponse> | null = null
let inflightFilterOptionsKey = ''

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

function setTrackedIds(ids: number[]) {
  const unique = [...new Set(ids.map(Number).filter((n) => Number.isFinite(n)))]
  trackedIds.value = unique
  persistTracked(unique, activeFilterDate)
}

function allFilterOptions(): LeagueFilterOption[] {
  const data = filterOptions.value
  if (!data) return []
  return [...data.configured, ...data.extra]
}

function syncTrackedWithFilterOptions() {
  const options = allFilterOptions()
  if (!options.length) return
  setTrackedIds(
    resolveTrackedSelection(options, readStoredIds(activeFilterDate) ?? []),
  )
}

async function loadFilterOptions(options?: {
  date?: string
}): Promise<LeagueFilterOptionsResponse> {
  const key = options?.date ?? ''
  if (inflightFilterOptions && inflightFilterOptionsKey === key) {
    return inflightFilterOptions
  }

  filterOptionsError.value = ''
  inflightFilterOptionsKey = key
  inflightFilterOptions = (async () => {
    try {
      const data = await fetchLeagueFilterOptions({
        date: options?.date,
      })
      filterOptions.value = data
      activeFilterDate = data.date
      syncTrackedWithFilterOptions()
      return data
    } catch (err) {
      filterOptionsError.value =
        err instanceof Error ? err.message : '加载联赛筛选选项失败'
      throw err
    } finally {
      inflightFilterOptions = null
      inflightFilterOptionsKey = ''
    }
  })()

  return inflightFilterOptions
}

export function useTrackedLeagues() {
  return {
    filterOptions,
    trackedIds,
    filterOptionsError,
    setTrackedIds,
    allFilterOptions,
    loadFilterOptions,
  }
}
