import { computed, ref } from 'vue'

import type {
  ResultFixture,
  ResultsAccuracy,
  ResultsHistoryResponse,
} from '@/api/fixtures'
import type { LeagueFilterOption } from '@/api/leagues'
import type { FixtureResponse, LeagueSummaryResponse } from '@/api/types'
import { leagueLabel } from '@/utils/leagueNames'
import { mergeDetailIntoListFixture } from '@/utils/oddsDisplay'

const resultsFixtures = ref<ResultFixture[]>([])
const scheduleFixtures = ref<FixtureResponse[]>([])
const scheduleMode = ref(false)
const resultsTrackedIds = ref<number[]>([])
const resultsLoading = ref(false)
const resultsLoadedDay = ref('')
const resultsAccuracy = ref<ResultsAccuracy | null>(null)
const resultsHistory = ref<ResultsHistoryResponse | null>(null)
const resultsByDay = new Map<
  string,
  { fixtures: ResultFixture[]; accuracy: ResultsAccuracy | null }
>()
const scheduleByDay = new Map<string, FixtureResponse[]>()

function setResultsTrackedIds(ids: number[]) {
  resultsTrackedIds.value = [...new Set(ids.map(Number).filter((n) => Number.isFinite(n)))]
}

type LeagueCountSeed = {
  league_id: number
  league_name: string
  country?: string | null
}

function buildFilterOptionsFromFixtures(
  fixtures: LeagueCountSeed[],
): LeagueFilterOption[] {
  const map = new Map<number, { name: string; country: string | null; count: number }>()
  for (const fx of fixtures) {
    const cur = map.get(fx.league_id)
    if (cur) cur.count += 1
    else {
      map.set(fx.league_id, {
        name: fx.league_name,
        country: fx.country ?? null,
        count: 1,
      })
    }
  }
  return [...map.entries()]
    .sort((a, b) =>
      leagueLabel(a[1].name).localeCompare(leagueLabel(b[1].name), 'zh'),
    )
    .map(([league_id, { name, country, count }]) => ({
      league_id,
      league_name: name,
      country,
      fixtures_count: count,
      tier: 'extra' as const,
      default_checked: true,
    }))
}

/** Each day defaults to all leagues on that day checked (no cross-day persistence). */
function syncResultsTrackedWithDay() {
  const options = scheduleMode.value
    ? buildFilterOptionsFromFixtures(
        scheduleFixtures.value.map((fx) => ({
          league_id: fx.league_id,
          league_name: fx.league_name,
        })),
      )
    : buildFilterOptionsFromFixtures(
        resultsFixtures.value.map((fx) => ({
          league_id: fx.league_id,
          league_name: fx.league_name,
          country: fx.league_country,
        })),
      )
  setResultsTrackedIds(options.map((o) => o.league_id))
}

/** Push finished fixtures for the selected day into the schedule shell. */
export function publishResultsFixtures(
  fixtures: ResultFixture[],
  day: string,
  accuracy?: ResultsAccuracy | null,
) {
  const dayChanged = day !== resultsLoadedDay.value
  const prevLeagueIds = new Set(resultsFixtures.value.map((fx) => fx.league_id))
  scheduleMode.value = false
  scheduleFixtures.value = []
  resultsFixtures.value = fixtures
  resultsLoadedDay.value = day
  if (accuracy !== undefined) resultsAccuracy.value = accuracy
  if (day) {
    resultsByDay.set(day, {
      fixtures: [...fixtures],
      accuracy: resultsAccuracy.value,
    })
  }
  if (dayChanged) {
    syncResultsTrackedWithDay()
    return
  }
  // Same-day capture may introduce leagues; keep user unchecks, auto-include newcomers.
  const added = [...new Set(fixtures.map((fx) => fx.league_id))].filter(
    (id) => !prevLeagueIds.has(id),
  )
  if (added.length) {
    setResultsTrackedIds([...resultsTrackedIds.value, ...added])
  }
}

/** Push upcoming fixtures for a future calendar day. */
export function publishScheduleFixtures(fixtures: FixtureResponse[], day: string) {
  const dayChanged = day !== resultsLoadedDay.value
  const pending = fixtures.filter((f) => f.status.toLowerCase() === 'pending')
  const prevLeagueIds = new Set(scheduleFixtures.value.map((fx) => fx.league_id))
  scheduleMode.value = true
  scheduleFixtures.value = pending
  resultsFixtures.value = []
  resultsAccuracy.value = null
  resultsLoadedDay.value = day
  if (day) scheduleByDay.set(day, [...pending])
  if (dayChanged) {
    syncResultsTrackedWithDay()
    return
  }
  const added = [...new Set(pending.map((fx) => fx.league_id))].filter(
    (id) => !prevLeagueIds.has(id),
  )
  if (added.length) {
    setResultsTrackedIds([...resultsTrackedIds.value, ...added])
  }
}

export function setResultsLoading(loading: boolean) {
  resultsLoading.value = loading
}

export function cacheResultsHistory(value: ResultsHistoryResponse | null) {
  resultsHistory.value = value
}

/** Restore an already visited day without another local API request. */
export function restoreCachedResultsDay(day: string, schedule: boolean): boolean {
  if (schedule) {
    const cached = scheduleByDay.get(day)
    if (!cached) return false
    publishScheduleFixtures(cached, day)
    return true
  }
  const cached = resultsByDay.get(day)
  if (!cached) return false
  publishResultsFixtures(cached.fixtures, day, cached.accuracy)
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

  const resultsFilterOptions = computed((): LeagueFilterOption[] =>
    scheduleMode.value
      ? buildFilterOptionsFromFixtures(
          scheduleFixtures.value.map((fx) => ({
            league_id: fx.league_id,
            league_name: fx.league_name,
          })),
        )
      : buildFilterOptionsFromFixtures(
          resultsFixtures.value.map((fx) => ({
            league_id: fx.league_id,
            league_name: fx.league_name,
            country: fx.league_country,
          })),
        ),
  )

  const countByLeague = computed(() => {
    const map = new Map<number, number>()
    const list = scheduleMode.value ? scheduleFixtures.value : resultsFixtures.value
    for (const fx of list) {
      if (!trackedIdSet.value.has(fx.league_id)) continue
      map.set(fx.league_id, (map.get(fx.league_id) || 0) + 1)
    }
    return map
  })

  const menuLeagues = computed((): LeagueSummaryResponse[] => {
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
    const list = scheduleMode.value ? scheduleFixtures.value : resultsFixtures.value
    let n = 0
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
    resultsAccuracy,
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
