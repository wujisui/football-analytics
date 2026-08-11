import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'

import { useFavoriteFixtures } from '@/composables/useFavoriteFixtures'
import {
  isPrematchListCacheFresh,
  useHomeFixtures,
} from '@/composables/useHomeFixtures'
import type { LeagueSummaryResponse } from '@/api/types'
import { useIsPhone, useIsTabletDown } from '@/composables/useMediaQuery'
import {
  ensureResultsConfiguredLeagueIds,
  useResultsLeagues,
} from '@/composables/useResultsLeagues'
import {
  endScheduleFilterOverride,
  getActiveFilterDate,
  useTrackedLeagues,
} from '@/composables/useTrackedLeagues'
import { sortFixturesFavoritesFirst } from '@/utils/fixtureSort'
import {
  fixturesShellContext,
  readFixturesLeagueFilter,
  writeFixturesLeagueFilter,
  type FixturesRouteName,
} from '@/utils/fixturesLeagueFilter'
import {
  isPrematchMatchDay,
  isScheduleFutureDay,
  predictionsDayCountLabel,
  prematchFetchParams,
  scheduleTodayDate,
  todayDate,
  yesterdayDate,
} from '@/utils/homeDateStrip'
import { toScheduleDayKey } from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'
import { filterByTeamQuery, teamSearchEmptyHint } from '@/utils/teamSearch'

const FIXTURES_ROUTE_NAMES = new Set<string>(['predictions', 'results'])

/**
 * Mobile browsers discard background tabs and reload on return; keep the
 * shell context for the browser session so that lands on the same view.
 */
const SHELL_STATE_KEY = 'fa-shell-state'

interface ShellSessionState {
  day: string
  teamSearch: string
}

function readShellSessionState(): Partial<ShellSessionState> {
  try {
    const raw = sessionStorage.getItem(SHELL_STATE_KEY)
    return raw ? (JSON.parse(raw) as Partial<ShellSessionState>) : {}
  } catch {
    return {}
  }
}

const restoredShellState = readShellSessionState()
/** Day was chosen earlier this session — pages must not reset to their default. */
export const hasSessionShellDay = typeof restoredShellState.day === 'string'

const selectedDay = ref(restoredShellState.day || yesterdayDate())
const prematchSelectedLeagueId = ref<number | null>(null)
const resultsSelectedLeagueId = ref<number | null>(null)
const teamSearch = ref(restoredShellState.teamSearch || '')

watch([selectedDay, teamSearch], () => {
  try {
    sessionStorage.setItem(
      SHELL_STATE_KEY,
      JSON.stringify({ day: selectedDay.value, teamSearch: teamSearch.value }),
    )
  } catch {
    /* private mode / quota — session restore just degrades */
  }
})

const siderCollapsed = ref(false)
const leagueDrawerShow = ref(false)

const resultsFilterRevision = ref(0)
const resultsFilterRevisionDay = ref('')

let shellWatchersBound = false

export function useFixturesShell() {
  const route = useRoute()
  const router = useRouter()
  const message = useMessage()
  const isPhone = useIsPhone()
  const isTabletDown = useIsTabletDown()

  const {
    allFixtures,
    loading: prematchLoading,
    error,
    loadHomeFixtures,
  } = useHomeFixtures()

  const { favoriteIds } = useFavoriteFixtures()

  const {
    trackedIds: prematchTrackedIds,
    filterOptionsError,
    setTrackedIds: setPrematchTrackedIds,
    allFilterOptions,
    loadFilterOptions,
  } = useTrackedLeagues()

  const {
    resultsTrackedIds,
    resultsFilterOptions,
    menuLeagues: resultsMenuLeagues,
    countByLeague: resultsCountByLeague,
    totalCount: resultsTotalCount,
    filterActive: resultsFilterActive,
    resultsLoading,
    confirmFilter: confirmResultsFilter,
    setResultsTrackedIds,
  } = useResultsLeagues()

  const pageName = computed(
    () => route.name as FixturesRouteName | undefined,
  )
  const isResultsPage = computed(() => pageName.value === 'results')
  const isScheduleFutureDayRef = computed(
    () => isResultsPage.value && isScheduleFutureDay(selectedDay.value, todayDate()),
  )
  const homeDay = computed(() => scheduleTodayDate())
  const shellContext = computed(() => fixturesShellContext(pageName.value))

  const selectedLeagueId = computed({
    get: () =>
      isResultsPage.value
        ? resultsSelectedLeagueId.value
        : prematchSelectedLeagueId.value,
    set: (id: number | null) => {
      if (isResultsPage.value) resultsSelectedLeagueId.value = id
      else prematchSelectedLeagueId.value = id
    },
  })

  const contentLoading = computed(() =>
    isResultsPage.value ? resultsLoading.value : prematchLoading.value,
  )

  const prematchTrackedIdSet = computed(() => new Set(prematchTrackedIds.value))
  const prematchFilterOptions = computed(() => allFilterOptions())
  const prematchFilterOptionById = computed(
    () => new Map(prematchFilterOptions.value.map((o) => [o.league_id, o])),
  )

  const prematchVisibleFixtures = computed(() => {
    const tracked = prematchTrackedIdSet.value
    const scheduleToday = scheduleTodayDate()
    return allFixtures.value.filter((f) => {
      if (!tracked.has(f.league_id)) return false
      return isPrematchMatchDay(toScheduleDayKey(f.fixture_date), scheduleToday)
    })
  })

  const prematchCountByLeague = computed(() => {
    const map = new Map<number, number>()
    for (const f of prematchVisibleFixtures.value) {
      map.set(f.league_id, (map.get(f.league_id) || 0) + 1)
    }
    return map
  })

  const prematchMenuLeagues = computed((): LeagueSummaryResponse[] => {
    const out: LeagueSummaryResponse[] = []
    const seen = new Set<number>()
    for (const f of prematchVisibleFixtures.value) {
      if (seen.has(f.league_id)) continue
      seen.add(f.league_id)
      const opt = prematchFilterOptionById.value.get(f.league_id)
      out.push({
        league_id: f.league_id,
        league_name: opt?.league_name || f.league_name || `League ${f.league_id}`,
        country: opt?.country ?? null,
        today_fixtures_count: 0,
        upcoming_fixtures_count: prematchCountByLeague.value.get(f.league_id) || 0,
      })
    }
    return out
  })

  const prematchFilterActive = computed(() => {
    const defaults = prematchFilterOptions.value
      .filter((o) => o.default_checked)
      .map((o) => o.league_id)
    if (!defaults.length && !prematchTrackedIds.value.length) return false
    if (prematchTrackedIds.value.length !== defaults.length) return true
    const tracked = prematchTrackedIdSet.value
    return defaults.some((id) => !tracked.has(id))
  })

  const shellTrackedIds = computed(() =>
    isResultsPage.value && !isScheduleFutureDayRef.value
      ? resultsTrackedIds.value
      : prematchTrackedIds.value,
  )
  const shellFilterOptions = computed(() =>
    isResultsPage.value && !isScheduleFutureDayRef.value
      ? resultsFilterOptions.value
      : prematchFilterOptions.value,
  )
  const shellFilterActive = computed(() =>
    isResultsPage.value && !isScheduleFutureDayRef.value
      ? resultsFilterActive.value
      : prematchFilterActive.value,
  )
  const shellMenuLeagues = computed(() =>
    isResultsPage.value ? resultsMenuLeagues.value : prematchMenuLeagues.value,
  )
  const shellCountByLeague = computed(() =>
    isResultsPage.value ? resultsCountByLeague.value : prematchCountByLeague.value,
  )
  const shellTotalCount = computed(() =>
    isResultsPage.value ? resultsTotalCount.value : prematchVisibleFixtures.value.length,
  )

  const selectedLeague = computed(() => {
    if (selectedLeagueId.value == null) return null
    return shellMenuLeagues.value.find((l) => l.league_id === selectedLeagueId.value) ?? null
  })

  const breadcrumbRoot = computed(() => {
    if (pageName.value === 'results') return '赛程'
    return '比赛'
  })

  const breadcrumbFilter = computed(() =>
    selectedLeague.value ? leagueLabel(selectedLeague.value.league_name) : '全部',
  )

  function leagueFiltered<T extends { league_id: number }>(list: T[]) {
    if (selectedLeagueId.value == null) return list
    return list.filter((f) => f.league_id === selectedLeagueId.value)
  }

  function sortFixtures<T extends { fixture_id: number; fixture_date: string }>(
    list: T[],
  ) {
    return sortFixturesFavoritesFirst(list, favoriteIds.value)
  }

  const prematchDisplayedFixtures = computed(() =>
    filterByTeamQuery(
      sortFixtures(leagueFiltered(prematchVisibleFixtures.value)),
      teamSearch.value,
    ),
  )

  /** Selected-day fixture count from filter-options / loaded list (league-aware). */
  const resultsDayFixtureCount = computed(() => {
    if (!isResultsPage.value) return 0
    if (selectedLeagueId.value == null) return shellTotalCount.value
    return shellCountByLeague.value.get(selectedLeagueId.value) || 0
  })

  const dayCountLabel = computed(() => {
    if (isResultsPage.value && !isScheduleFutureDayRef.value) return ''
    if (isScheduleFutureDayRef.value) {
      return predictionsDayCountLabel(resultsDayFixtureCount.value)
    }
    const list = leagueFiltered(prematchVisibleFixtures.value)
    const count = filterByTeamQuery(sortFixtures(list), teamSearch.value).length
    return predictionsDayCountLabel(count)
  })

  const predictionsEmptyText = computed(() => {
    if (error.value) return ''
    const day = scheduleTodayDate()
    if (!prematchTrackedIds.value.length) return '请先在「筛选」中勾选联赛'
    if (!prematchDisplayedFixtures.value.length && !teamSearch.value.trim()) {
      return `${day} 暂无未开赛赛事`
    }
    const teamHint = teamSearchEmptyHint(teamSearch.value)
    if (teamHint && sortFixtures(leagueFiltered(prematchVisibleFixtures.value)).length) {
      return teamHint
    }
    return `${day} 暂无未开赛赛事`
  })

  function syncLeagueFromRoute() {
    const ctx = fixturesShellContext(route.name as FixturesRouteName)
    const target =
      ctx === 'results' ? resultsSelectedLeagueId : prematchSelectedLeagueId

    const fromQuery = route.query.league
    if (fromQuery === 'all') {
      target.value = null
      writeFixturesLeagueFilter(null, ctx)
      return
    }
    if (fromQuery != null && fromQuery !== '') {
      const id = Number(fromQuery)
      if (!Number.isNaN(id)) {
        target.value = id
        writeFixturesLeagueFilter(id, ctx)
        return
      }
    }
    const stored = readFixturesLeagueFilter(ctx)
    target.value = stored
    const name = route.name
    if (
      stored != null &&
      FIXTURES_ROUTE_NAMES.has(String(name)) &&
      route.query.league !== String(stored)
    ) {
      void router.replace({
        name: name as FixturesRouteName,
        query: { league: String(stored) },
      })
    }
  }

  function syncFutureScheduleSelection() {
    if (!isScheduleFutureDayRef.value || !prematchTrackedIds.value.length) return
    setResultsTrackedIds(prematchTrackedIds.value)
  }

  /** Prematch list only — never write 赛程 selectedDay into shared allFixtures. */
  async function loadDayLocal(force = false) {
    const { date, days } = prematchFetchParams()
    try {
      await loadHomeFixtures({
        force,
        date,
        days,
        leagueIds: [...prematchTrackedIds.value],
      })
      syncLeagueFromRoute()
    } catch {
      // error already set in composable
    }
  }

  async function reloadPrematchDay(force = false) {
    try {
      await loadFilterOptions({ date: homeDay.value, scope: 'prematch' })
    } catch {
      if (filterOptionsError.value) message.warning(filterOptionsError.value)
    }
    await loadDayLocal(force)
  }

  /** Leave 赛程: restore frozen calculator filter, then refresh list/filter if stale. */
  function restorePrematchAfterResults() {
    endScheduleFilterOverride()
    const force =
      getActiveFilterDate() !== homeDay.value ||
      !isPrematchListCacheFresh(undefined, prematchTrackedIds.value)
    void reloadPrematchDay(force)
  }

  async function confirmFilter(ids: number[]) {
    if (isResultsPage.value && isScheduleFutureDayRef.value) {
      const allow = new Set(prematchFilterOptions.value.map((o) => o.league_id))
      const allowed = ids.filter((id) => allow.has(id))
      if (!allowed.length) {
        message.warning('请至少勾选一个默认或可选联赛')
        return
      }
      setPrematchTrackedIds(allowed)
      setResultsTrackedIds(allowed)
      if (
        resultsSelectedLeagueId.value != null &&
        !allowed.includes(resultsSelectedLeagueId.value)
      ) {
        selectLeague(null)
      }
      resultsFilterRevisionDay.value = selectedDay.value
      resultsFilterRevision.value += 1
      return
    }
    if (isResultsPage.value) {
      const ok = confirmResultsFilter(ids)
      if (!ok) {
        message.warning('请至少勾选一个完场联赛')
        return
      }
      if (
        resultsSelectedLeagueId.value != null &&
        !ids.includes(resultsSelectedLeagueId.value)
      ) {
        selectLeague(null)
      }
      resultsFilterRevisionDay.value = selectedDay.value
      resultsFilterRevision.value += 1
      return
    }

    const allow = new Set(prematchFilterOptions.value.map((o) => o.league_id))
    const allowed = ids.filter((id) => allow.has(id))
    if (!allowed.length) {
      message.warning('请至少勾选一个今日有赛的联赛')
      return
    }
    setPrematchTrackedIds(allowed)
    if (
      prematchSelectedLeagueId.value != null &&
      !allowed.includes(prematchSelectedLeagueId.value)
    ) {
      selectLeague(null)
    }
    await loadDayLocal(true)
  }

  function selectLeague(leagueId: number | null) {
    selectedLeagueId.value = leagueId
    writeFixturesLeagueFilter(leagueId, shellContext.value)
    leagueDrawerShow.value = false
    const name = route.name
    if (!FIXTURES_ROUTE_NAMES.has(String(name))) return
    router.replace({
      name: name as FixturesRouteName,
      query: leagueId == null ? {} : { league: String(leagueId) },
    })
  }

  if (!shellWatchersBound) {
    shellWatchersBound = true

    watch(
      isTabletDown,
      (compact) => {
        if (compact && !isPhone.value) siderCollapsed.value = true
      },
      { immediate: true },
    )

    void ensureResultsConfiguredLeagueIds()

    watch(prematchTrackedIds, () => {
      syncFutureScheduleSelection()
      if (
        !isResultsPage.value &&
        prematchSelectedLeagueId.value != null &&
        !prematchTrackedIdSet.value.has(prematchSelectedLeagueId.value)
      ) {
        selectLeague(null)
      }
    })

    watch(resultsTrackedIds, () => {
      if (
        isResultsPage.value &&
        resultsSelectedLeagueId.value != null &&
        !new Set(resultsTrackedIds.value).has(resultsSelectedLeagueId.value)
      ) {
        selectLeague(null)
      }
    })

    watch(resultsMenuLeagues, () => {
      if (
        !isResultsPage.value ||
        resultsSelectedLeagueId.value == null ||
        !resultsMenuLeagues.value.length
      ) {
        return
      }
      if (
        !resultsMenuLeagues.value.some(
          (l) => l.league_id === resultsSelectedLeagueId.value,
        )
      ) {
        selectLeague(null)
      }
    })

    watch(prematchMenuLeagues, () => {
      if (
        isResultsPage.value ||
        prematchSelectedLeagueId.value == null ||
        !prematchMenuLeagues.value.length
      ) {
        return
      }
      if (
        !prematchMenuLeagues.value.some(
          (l) => l.league_id === prematchSelectedLeagueId.value,
        )
      ) {
        selectLeague(null)
      }
    })

    watch(
      () => route.query.league,
      () => {
        if (!FIXTURES_ROUTE_NAMES.has(String(route.name))) return
        syncLeagueFromRoute()
      },
    )

    watch(
      () => route.name,
      (name, prev) => {
        syncLeagueFromRoute()
        const prematch = name === 'predictions'
        if (prematch && prev === 'results') {
          restorePrematchAfterResults()
        }
      },
    )
  }

  return {
    selectedDay,
    selectedLeagueId,
    teamSearch,
    siderCollapsed,
    leagueDrawerShow,
    contentLoading,
    error,
    shellTrackedIds,
    shellFilterOptions,
    shellFilterActive,
    shellMenuLeagues,
    shellCountByLeague,
    shellTotalCount,
    breadcrumbRoot,
    breadcrumbFilter,
    dayCountLabel,
    resultsDayFixtureCount,
    prematchDisplayedFixtures,
    predictionsEmptyText,
    resultsFilterRevision,
    resultsFilterRevisionDay,
    reloadPrematchDay,
    loadFilterOptions,
    syncFutureScheduleSelection,
    confirmFilter,
    selectLeague,
    syncLeagueFromRoute,
    isResultsPage,
    isScheduleFutureDay: isScheduleFutureDayRef,
    homeDay,
  }
}

export function bootstrapFixturesShell(options?: { reloadPrematch?: boolean }) {
  const { syncLeagueFromRoute, reloadPrematchDay } = useFixturesShell()
  syncLeagueFromRoute()
  if (options?.reloadPrematch) void reloadPrematchDay()
}
