import { computed, ref, watch } from 'vue'

import { useHandicapRuleset } from '@/composables/useHandicapRuleset'

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
 * filter-options for results covers finished + live that day, so past 完场 days
 * would incorrectly clear this set if we derived it from there.
 */
const configuredLeagueIds = ref<Set<number>>(new Set())
const configuredIdsReady = ref(false)
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

/** Load admin 热门 ids once for 热门 grouping on 赛程. */
export async function ensureResultsConfiguredLeagueIds(): Promise<void> {
  if (configuredIdsReady.value) return
  if (configuredIdsInflight) return configuredIdsInflight
  configuredIdsInflight = (async () => {
    try {
      const data = await fetchLeagueCatalog()
      setResultsConfiguredLeagueIds(
        data.leagues.filter((item) => item.hot).map((item) => item.league_id),
      )
      configuredIdsReady.value = true
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

export function invalidateFinishedResultsCache() {
  resultsByDay.clear()
  resultsHistory.value = null
}

const { ruleset: handicapRuleset } = useHandicapRuleset()
watch(handicapRuleset, () => {
  invalidateFinishedResultsCache()
})

function detailHasFinishedScore(detail: FixtureResponse): boolean {
  return (
    (detail.status || '').toLowerCase() === 'finished' &&
    detail.home_goals != null &&
    detail.away_goals != null
  )
}

/** List row already shows FT — opening detail is read-only, not a settlement event. */
function listRowAlreadyFinished(row: ResultFixture): boolean {
  return (
    (row.status || '').toLowerCase() === 'finished' &&
    row.home_goals != null &&
    row.away_goals != null
  )
}

/**
 * Only when detail newly supplies FT for a row that was still open/live in the
 * list cache do we need to re-evaluate hit flags and rebuild history/charts.
 */
function needsSettlementReload(
  prev: ResultFixture,
  detail: FixtureResponse,
): boolean {
  return detailHasFinishedScore(detail) && !listRowAlreadyFinished(prev)
}

function mergeDetailScoreIntoResult(
  prev: ResultFixture,
  detail: FixtureResponse,
): ResultFixture {
  const next: ResultFixture = {
    ...prev,
    status: detail.status,
    home_goals: detail.home_goals ?? prev.home_goals,
    away_goals: detail.away_goals ?? prev.away_goals,
    home_rank: detail.home_rank ?? prev.home_rank,
    away_rank: detail.away_rank ?? prev.away_rank,
  }
  // Newly finished via detail — clear hit flags so list reload regrades from DB.
  // Already-finished rows keep existing flags (viewing detail is not a settlement).
  if (needsSettlementReload(prev, detail)) {
    next.handicap_result = null
    next.handicap_hit = null
    next.score_hit = null
    next.ou_hit = null
    next.btts_hit = null
    next.result_hit = null
    next.auto_pick_hit = null
  }
  return next
}

/** Days whose score patch still needs a local results reload for hit flags. */
const settlementDirtyDays = new Set<string>()

/** True when returning to 赛果 should force-reload the selected day. */
export function consumeResultsSettlementDirty(day: string): boolean {
  if (!settlementDirtyDays.has(day)) return false
  settlementDirtyDays.delete(day)
  return true
}

/**
 * Detail click may pull the latest official score. Always patch score/status
 * into the list cache. Only when the list row was not yet finished do we drop
 * that day's cache + history so the next 赛果 visit regrades hit flags.
 */
export function patchResultsFixtureFromDetail(detail: FixtureResponse): void {
  const daysTouched = new Set<string>()
  let needsSettlement = false
  let touchedResults = false

  function patchRows(rows: ResultFixture[]): ResultFixture[] {
    return rows.map((row) => {
      if (row.fixture_id !== detail.fixture_id) return row
      if (needsSettlementReload(row, detail)) needsSettlement = true
      return mergeDetailScoreIntoResult(row, detail)
    })
  }

  for (const [day, rows] of resultsByDay) {
    const idx = rows.findIndex((f) => f.fixture_id === detail.fixture_id)
    if (idx < 0) continue
    daysTouched.add(day)
    const next = patchRows(rows)
    resultsByDay.set(day, next)
    if (!scheduleMode.value && resultsLoadedDay.value === day) {
      resultsFixtures.value = next
      touchedResults = true
    }
  }
  if (!touchedResults) {
    const idx = resultsFixtures.value.findIndex(
      (f) => f.fixture_id === detail.fixture_id,
    )
    if (idx >= 0) {
      if (resultsLoadedDay.value) daysTouched.add(resultsLoadedDay.value)
      resultsFixtures.value = patchRows(resultsFixtures.value)
    }
  }

  if (needsSettlement && daysTouched.size) {
    for (const day of daysTouched) {
      settlementDirtyDays.add(day)
      resultsByDay.delete(day)
    }
    // Accuracy series grades newly finished rows — rebuild on next visit.
    resultsHistory.value = null
    if (
      !scheduleMode.value &&
      daysTouched.has(resultsLoadedDay.value)
    ) {
      // Force onActivated / next loadSelectedDay to refetch and settle hits.
      resultsLoadedDay.value = ''
    }
  }

  let touchedSchedule = false
  for (const [day, rows] of scheduleByDay) {
    const idx = rows.findIndex((f) => f.fixture_id === detail.fixture_id)
    if (idx < 0) continue
    const next = rows.map((row, i) =>
      i === idx ? mergeDetailIntoListFixture(row, detail) : row,
    )
    scheduleByDay.set(day, next)
    if (scheduleMode.value && resultsLoadedDay.value === day) {
      scheduleFixtures.value = next
      touchedSchedule = true
    }
  }
  if (touchedSchedule) return
  const idx = scheduleFixtures.value.findIndex(
    (f) => f.fixture_id === detail.fixture_id,
  )
  if (idx < 0) return
  scheduleFixtures.value = scheduleFixtures.value.map((row, i) =>
    i === idx ? mergeDetailIntoListFixture(row, detail) : row,
  )
}

/** Instant detail crumb while /analysis is still in flight. */
export function findResultsListFixture(
  fixtureId: number,
): ResultFixture | FixtureResponse | null {
  const fromResults =
    resultsFixtures.value.find((f) => f.fixture_id === fixtureId) ??
    [...resultsByDay.values()]
      .flat()
      .find((f) => f.fixture_id === fixtureId)
  if (fromResults) return fromResults
  return (
    scheduleFixtures.value.find((f) => f.fixture_id === fixtureId) ??
    [...scheduleByDay.values()]
      .flat()
      .find((f) => f.fixture_id === fixtureId) ??
    null
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
