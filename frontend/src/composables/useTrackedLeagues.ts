import { ref } from 'vue'

import {
  fetchLeagueFilterOptions,
  type LeagueCatalogItem,
  type LeagueFilterOption,
  type LeagueFilterOptionsResponse,
} from '@/api/leagues'

const STORAGE_KEY = 'fa-tracked-league-ids'

const catalog = ref<LeagueCatalogItem[]>([])
const filterOptions = ref<LeagueFilterOptionsResponse | null>(null)
const trackedIds = ref<number[]>([])
const filterOptionsError = ref('')

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

/** Prune preference to current options; default = configured (default_checked) only. */
function syncTrackedWithFilterOptions() {
  const options = allFilterOptions()
  const allow = new Set(options.map((o) => o.league_id))
  const defaults = options.filter((o) => o.default_checked).map((o) => o.league_id)
  const stored = readStoredIds()
  if (stored?.length) {
    const pruned = stored.filter((id) => allow.has(id))
    if (pruned.length) {
      setTrackedIds(pruned)
      return
    }
  }
  setTrackedIds(defaults)
}

async function loadFilterOptions(options?: {
  date?: string
  discover?: boolean
}): Promise<LeagueFilterOptionsResponse> {
  filterOptionsError.value = ''
  try {
    const data = await fetchLeagueFilterOptions({
      date: options?.date,
      discover: options?.discover ?? true,
    })
    filterOptions.value = data
    if (data.catalog?.length) {
      catalog.value = data.catalog
    }
    syncTrackedWithFilterOptions()
    return data
  } catch (err) {
    filterOptionsError.value =
      err instanceof Error ? err.message : '加载联赛筛选选项失败'
    throw err
  }
}

export function useTrackedLeagues() {
  return {
    catalog,
    filterOptions,
    trackedIds,
    filterOptionsError,
    setTrackedIds,
    allFilterOptions,
    loadFilterOptions,
  }
}
