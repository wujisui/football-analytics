import { ref } from 'vue'

import {
  fetchLeagueFilterOptions,
  type LeagueFilterOption,
  type LeagueFilterOptionsResponse,
} from '@/api/leagues'
import { resolveTrackedSelection } from '@/utils/leagueFilterSelection'

const STORAGE_KEY = 'fa-tracked-league-ids'

const filterOptions = ref<LeagueFilterOptionsResponse | null>(null)
const trackedIds = ref<number[]>([])
const filterOptionsError = ref('')

let inflightFilterOptions: Promise<LeagueFilterOptionsResponse> | null = null
let inflightFilterOptionsKey = ''

function readStoredIds(): number[] | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return null
    return parsed.map(Number).filter((n) => Number.isFinite(n))
  } catch {
    return null
  }
}

function persistTracked(ids: number[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids))
  } catch {
    /* ignore */
  }
}

function setTrackedIds(ids: number[]) {
  const unique = [...new Set(ids.map(Number).filter((n) => Number.isFinite(n)))]
  trackedIds.value = unique
  persistTracked(unique)
}

function allFilterOptions(): LeagueFilterOption[] {
  const data = filterOptions.value
  if (!data) return []
  return [...data.configured, ...data.extra]
}

function syncTrackedWithFilterOptions() {
  const options = allFilterOptions()
  if (!options.length) return
  setTrackedIds(resolveTrackedSelection(options, readStoredIds() ?? []))
}

async function loadFilterOptions(options?: {
  date?: string
  discover?: boolean
}): Promise<LeagueFilterOptionsResponse> {
  const key = `${options?.date ?? ''}|${options?.discover ?? true}`
  if (inflightFilterOptions && inflightFilterOptionsKey === key) {
    return inflightFilterOptions
  }

  filterOptionsError.value = ''
  inflightFilterOptionsKey = key
  inflightFilterOptions = (async () => {
    try {
      const data = await fetchLeagueFilterOptions({
        date: options?.date,
        discover: options?.discover ?? true,
      })
      filterOptions.value = data
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
