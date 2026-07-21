import { computed, ref } from 'vue'

import type { ResultFixture } from '@/api/fixtures'
import type { LeagueFilterOption } from '@/api/leagues'
import type { FixtureResponse, LeagueSummaryResponse } from '@/api/types'
import { leagueLabel } from '@/utils/leagueNames'

const resultsFixtures = ref<ResultFixture[]>([])
const scheduleFixtures = ref<FixtureResponse[]>([])
const scheduleMode = ref(false)
const resultsTrackedIds = ref<number[]>([])
const resultsLoading = ref(false)
const resultsLoadedDay = ref('')

function setResultsTrackedIds(ids: number[]) {
  resultsTrackedIds.value = [...new Set(ids.map(Number).filter((n) => Number.isFinite(n)))]
}

function buildFilterOptionsFromResults(
  fixtures: ResultFixture[],
): LeagueFilterOption[] {
  const map = new Map<number, { name: string; country: string | null; count: number }>()
  for (const fx of fixtures) {
    const cur = map.get(fx.league_id)
    if (cur) cur.count += 1
    else {
      map.set(fx.league_id, {
        name: fx.league_name,
        country: fx.league_country ?? null,
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
      locally_loaded: true,
    }))
}

function buildFilterOptionsFromSchedule(
  fixtures: FixtureResponse[],
): LeagueFilterOption[] {
  const map = new Map<number, { name: string; count: number }>()
  for (const fx of fixtures) {
    const cur = map.get(fx.league_id)
    if (cur) cur.count += 1
    else {
      map.set(fx.league_id, { name: fx.league_name, count: 1 })
    }
  }
  return [...map.entries()]
    .sort((a, b) =>
      leagueLabel(a[1].name).localeCompare(leagueLabel(b[1].name), 'zh'),
    )
    .map(([league_id, { name, count }]) => ({
      league_id,
      league_name: name,
      country: null,
      fixtures_count: count,
      tier: 'extra' as const,
      default_checked: true,
      locally_loaded: true,
    }))
}

/** Each day defaults to all leagues on that day checked (no cross-day persistence). */
function syncResultsTrackedWithDay() {
  const options = scheduleMode.value
    ? buildFilterOptionsFromSchedule(scheduleFixtures.value)
    : buildFilterOptionsFromResults(resultsFixtures.value)
  setResultsTrackedIds(options.map((o) => o.league_id))
}

/** Push finished fixtures for the selected day into the schedule shell. */
export function publishResultsFixtures(fixtures: ResultFixture[], day: string) {
  const dayChanged = day !== resultsLoadedDay.value
  scheduleMode.value = false
  scheduleFixtures.value = []
  resultsFixtures.value = fixtures
  resultsLoadedDay.value = day
  if (dayChanged) {
    syncResultsTrackedWithDay()
  }
}

/** Push upcoming fixtures for a future calendar day. */
export function publishScheduleFixtures(fixtures: FixtureResponse[], day: string) {
  const dayChanged = day !== resultsLoadedDay.value
  scheduleMode.value = true
  scheduleFixtures.value = fixtures.filter((f) => f.status.toLowerCase() === 'pending')
  resultsFixtures.value = []
  resultsLoadedDay.value = day
  if (dayChanged) {
    syncResultsTrackedWithDay()
  }
}

export function setResultsLoading(loading: boolean) {
  resultsLoading.value = loading
}

export function useResultsLeagues() {
  const trackedIdSet = computed(() => new Set(resultsTrackedIds.value))

  const resultsFilterOptions = computed((): LeagueFilterOption[] =>
    scheduleMode.value
      ? buildFilterOptionsFromSchedule(scheduleFixtures.value)
      : buildFilterOptionsFromResults(resultsFixtures.value),
  )

  const countByLeague = computed(() => {
    const map = new Map<number, number>()
    if (scheduleMode.value) {
      for (const fx of scheduleFixtures.value) {
        if (!trackedIdSet.value.has(fx.league_id)) continue
        map.set(fx.league_id, (map.get(fx.league_id) || 0) + 1)
      }
      return map
    }
    for (const fx of resultsFixtures.value) {
      if (!trackedIdSet.value.has(fx.league_id)) continue
      map.set(fx.league_id, (map.get(fx.league_id) || 0) + 1)
    }
    return map
  })

  const menuLeagues = computed((): LeagueSummaryResponse[] => {
    if (scheduleMode.value) {
      const map = new Map<number, LeagueSummaryResponse>()
      for (const fx of scheduleFixtures.value) {
        if (!trackedIdSet.value.has(fx.league_id)) continue
        if (map.has(fx.league_id)) continue
        map.set(fx.league_id, {
          league_id: fx.league_id,
          league_name: fx.league_name,
          country: null,
          today_fixtures_count: 0,
          upcoming_fixtures_count: countByLeague.value.get(fx.league_id) || 0,
        })
      }
      return [...map.values()].sort((a, b) =>
        leagueLabel(a.league_name).localeCompare(leagueLabel(b.league_name), 'zh'),
      )
    }
    const map = new Map<number, LeagueSummaryResponse>()
    for (const fx of resultsFixtures.value) {
      if (!trackedIdSet.value.has(fx.league_id)) continue
      if (map.has(fx.league_id)) continue
      map.set(fx.league_id, {
        league_id: fx.league_id,
        league_name: fx.league_name,
        country: fx.league_country ?? null,
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
    if (scheduleMode.value) {
      for (const fx of scheduleFixtures.value) {
        if (trackedIdSet.value.has(fx.league_id)) n += 1
      }
      return n
    }
    for (const fx of resultsFixtures.value) {
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
    resultsTrackedIds,
    resultsLoading,
    resultsFilterOptions,
    menuLeagues,
    countByLeague,
    totalCount,
    filterActive,
    confirmFilter,
  }
}
