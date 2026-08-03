import { computed, ref } from 'vue'

import type { ResultFixture, ResultsHistoryResponse } from '@/api/fixtures'
import {
  fetchLeagueCatalog,
  fetchLeagueFilterOptions,
  type LeagueFilterOption,
} from '@/api/leagues'
import type { FixtureResponse, LeagueSummaryResponse } from '@/api/types'
import { resolveTrackedSelection } from '@/utils/leagueFilterSelection'
import { leagueLabel } from '@/utils/leagueNames'
import { mergeDetailIntoListFixture } from '@/utils/oddsDisplay'

const RESULTS_TRACKED_KEY = 'fa-results-tracked-league-ids-by-date-v1'

const resultsFixtures = ref<ResultFixture[]>([])
const scheduleFixtures = ref<FixtureResponse[]>([])
const scheduleMode = ref(false)
const resultsTrackedIds = ref<number[]>([])
const resultsFilterOptions = ref<LeagueFilterOption[]>([])
const resultsLoading = ref(false)
const resultsLoadedDay = ref('')
/** Date of the last filter-options payload — used to keep user checks within a day. */
const resultsFilterOptionsDay = ref('')
const resultsHistory = ref<ResultsHistoryResponse | null>(null)
const resultsByDay = new Map<string, ResultFixture[]>()
const scheduleByDay = new Map<string, FixtureResponse[]>()

/**
 * Primary (热门) league ids from /leagues/catalog — not day filter-options.
 * filter-options only lists unfinished fixtures that day, so past 完场 days
 * would incorrectly clear this set if we derived it from there.
 */
const configuredLeagueIds = ref<Set<number>>(new Set())
let configuredIdsInflight: Promise<void> | null = null

function readStoredResultsTracked(date: string): number[] | null {
  if (!date) return null
  try {
    const raw = localStorage.getItem(RESULTS_TRACKED_KEY)
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

function persistResultsTracked(ids: number[], date: string) {
  if (!date) return
  try {
    const raw = localStorage.getItem(RESULTS_TRACKED_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    const byDate =
      parsed && typeof parsed === 'object' && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : {}
    byDate[date] = ids
    localStorage.setItem(RESULTS_TRACKED_KEY, JSON.stringify(byDate))
  } catch {
    /* ignore */
  }
}

function setResultsConfiguredLeagueIds(ids: Iterable<number>) {
  configuredLeagueIds.value = new Set(
    [...ids].map(Number).filter((n) => Number.isFinite(n)),
  )
}

/** Load leagues.json primary catalog once for 热门 grouping on 赛程. */
export async function ensureResultsConfiguredLeagueIds(): Promise<void> {
  if (configuredLeagueIds.value.size > 0) return
  if (configuredIdsInflight) return configuredIdsInflight
  configuredIdsInflight = (async () => {
    try {
      const data = await fetchLeagueCatalog()
      setResultsConfiguredLeagueIds(data.leagues.map((l) => l.league_id))
    } catch {
      /* keep empty; filter falls back to 其他 only */
    } finally {
      configuredIdsInflight = null
    }
  })()
  return configuredIdsInflight
}

function setResultsTrackedIds(ids: number[]) {
  const unique = [...new Set(ids.map(Number).filter((n) => Number.isFinite(n)))]
  resultsTrackedIds.value = unique
  const day = resultsFilterOptionsDay.value || resultsLoadedDay.value
  if (day) persistResultsTracked(unique, day)
}

/**
 * Lightweight league checklist for a results/schedule day (counts only).
 * Sets tracked ids from stored preference ∩ options (defaults = primary).
 */
export async function loadResultsFilterOptions(options: {
  date: string
  schedule: boolean
}): Promise<LeagueFilterOption[]> {
  const data = await fetchLeagueFilterOptions({
    date: options.date,
    scope: options.schedule ? 'prematch' : 'results',
  })
  const list = [...data.configured, ...data.extra]
  resultsFilterOptions.value = list
  const allow = new Set(list.map((o) => o.league_id))
  const sameDay = resultsFilterOptionsDay.value === options.date
  const kept = sameDay
    ? resultsTrackedIds.value.filter((id) => allow.has(id))
    : []
  resultsFilterOptionsDay.value = options.date
  if (kept.length) {
    setResultsTrackedIds(kept)
  } else {
    setResultsTrackedIds(
      resolveTrackedSelection(list, readStoredResultsTracked(options.date) ?? []),
    )
  }
  return list
}

/** Push finished fixtures for the selected day into the schedule shell. */
export function publishResultsFixtures(fixtures: ResultFixture[], day: string) {
  scheduleMode.value = false
  scheduleFixtures.value = []
  resultsFixtures.value = fixtures
  resultsLoadedDay.value = day
  if (day) resultsByDay.set(day, [...fixtures])
}

/** Push upcoming fixtures for a future calendar day. */
export function publishScheduleFixtures(fixtures: FixtureResponse[], day: string) {
  const pending = fixtures.filter((f) => f.status.toLowerCase() === 'pending')
  scheduleMode.value = true
  scheduleFixtures.value = pending
  resultsFixtures.value = []
  resultsLoadedDay.value = day
  if (day) scheduleByDay.set(day, [...pending])
}

export function setResultsLoading(loading: boolean) {
  resultsLoading.value = loading
}

export function cacheResultsHistory(value: ResultsHistoryResponse | null) {
  resultsHistory.value = value
}

/** Restore an already visited day without another local API request. */
export function restoreCachedResultsDay(day: string, schedule: boolean): boolean {
  // Day counts (tab badge, sidebar) come from the league checklist. Reusing a
  // cached list while the checklist still describes another day would keep
  // showing that day's numbers.
  if (resultsFilterOptionsDay.value !== day) return false
  if (schedule) {
    const cached = scheduleByDay.get(day)
    if (!cached) return false
    publishScheduleFixtures(cached, day)
    return true
  }
  const cached = resultsByDay.get(day)
  if (!cached) return false
  publishResultsFixtures(cached, day)
  return true
}

export function invalidateCachedResultsDay(day: string, schedule: boolean) {
  if (schedule) scheduleByDay.delete(day)
  else resultsByDay.delete(day)
}

/**
 * After detail pulls odds/analysis, merge into schedule day caches so
 * returning to 赛程 future days shows the snippet (same as 即时 list).
 */
export function patchScheduleFixtureFromDetail(detail: FixtureResponse): void {
  let touchedLive = false
  for (const [day, rows] of scheduleByDay) {
    const idx = rows.findIndex((f) => f.fixture_id === detail.fixture_id)
    if (idx < 0) continue
    const next = rows.map((row, i) =>
      i === idx ? mergeDetailIntoListFixture(row, detail) : row,
    )
    scheduleByDay.set(day, next)
    if (scheduleMode.value && resultsLoadedDay.value === day) {
      scheduleFixtures.value = next
      touchedLive = true
    }
  }
  if (touchedLive) return
  const idx = scheduleFixtures.value.findIndex(
    (f) => f.fixture_id === detail.fixture_id,
  )
  if (idx < 0) return
  scheduleFixtures.value = scheduleFixtures.value.map((row, i) =>
    i === idx ? mergeDetailIntoListFixture(row, detail) : row,
  )
}

export function useResultsLeagues() {
  const trackedIdSet = computed(() => new Set(resultsTrackedIds.value))

  /**
   * Server counts describe the checklist's day. Only trust them while that is
   * the day on screen, so counts can never report another date.
   */
  const dayCountsFromServer = computed(
    () =>
      !resultsLoadedDay.value ||
      resultsFilterOptionsDay.value === resultsLoadedDay.value,
  )

  const countByLeague = computed(() => {
    const map = new Map<number, number>()
    // Prefer server count from filter-options (covers unchecked leagues too).
    if (dayCountsFromServer.value) {
      for (const opt of resultsFilterOptions.value) {
        if (!trackedIdSet.value.has(opt.league_id)) continue
        map.set(opt.league_id, opt.fixtures_count)
      }
      if (map.size) return map
    }
    const list = scheduleMode.value ? scheduleFixtures.value : resultsFixtures.value
    for (const fx of list) {
      if (!trackedIdSet.value.has(fx.league_id)) continue
      map.set(fx.league_id, (map.get(fx.league_id) || 0) + 1)
    }
    return map
  })

  const menuLeagues = computed((): LeagueSummaryResponse[] => {
    const fromOptions = resultsFilterOptions.value.filter((o) =>
      trackedIdSet.value.has(o.league_id),
    )
    if (fromOptions.length) {
      return fromOptions
        .map((o) => ({
          league_id: o.league_id,
          league_name: o.league_name,
          country: o.country,
          today_fixtures_count: 0,
          upcoming_fixtures_count: o.fixtures_count,
        }))
        .sort((a, b) =>
          leagueLabel(a.league_name).localeCompare(leagueLabel(b.league_name), 'zh'),
        )
    }
    const list = scheduleMode.value ? scheduleFixtures.value : resultsFixtures.value
    const map = new Map<number, LeagueSummaryResponse>()
    for (const fx of list) {
      if (!trackedIdSet.value.has(fx.league_id)) continue
      if (map.has(fx.league_id)) continue
      map.set(fx.league_id, {
        league_id: fx.league_id,
        league_name: fx.league_name,
        country: scheduleMode.value
          ? null
          : ((fx as ResultFixture).league_country ?? null),
        today_fixtures_count: 0,
        upcoming_fixtures_count: countByLeague.value.get(fx.league_id) || 0,
      })
    }
    return [...map.values()].sort((a, b) =>
      leagueLabel(a.league_name).localeCompare(leagueLabel(b.league_name), 'zh'),
    )
  })

  const totalCount = computed(() => {
    let n = 0
    if (dayCountsFromServer.value) {
      for (const opt of resultsFilterOptions.value) {
        if (trackedIdSet.value.has(opt.league_id)) n += opt.fixtures_count
      }
      if (n) return n
    }
    const list = scheduleMode.value ? scheduleFixtures.value : resultsFixtures.value
    for (const fx of list) {
      if (trackedIdSet.value.has(fx.league_id)) n += 1
    }
    return n
  })

  const filterActive = computed(() => {
    const all = resultsFilterOptions.value.map((o) => o.league_id)
    if (!all.length) return false
    if (resultsTrackedIds.value.length !== all.length) return true
    return all.some((id) => !trackedIdSet.value.has(id))
  })

  function confirmFilter(ids: number[]) {
    const allow = new Set(resultsFilterOptions.value.map((o) => o.league_id))
    const allowed = ids.filter((id) => allow.has(id))
    if (!allowed.length) return false
    setResultsTrackedIds(allowed)
    return true
  }

  return {
    resultsFixtures,
    scheduleFixtures,
    scheduleMode,
    resultsLoadedDay,
    resultsHistory,
    resultsTrackedIds,
    setResultsTrackedIds,
    resultsLoading,
    resultsFilterOptions,
    menuLeagues,
    countByLeague,
    totalCount,
    filterActive,
    confirmFilter,
  }
}
