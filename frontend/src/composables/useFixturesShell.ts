import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'

import type { SyncFixturesOptions } from '@/api/fixtures'
import { enqueueBackgroundSync } from '@/composables/useBackgroundSync'
import { markDayAutoSynced, isDayAutoSynced, shouldAutoSyncDay, shouldGapFillOdds, markOddsGapFillTried, clearOddsGapFillTried } from '@/composables/useDayAutoSync'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import type { LeagueSummaryResponse } from '@/api/types'
import { useIsPhone, useIsTabletDown } from '@/composables/useMediaQuery'
import { useResultsLeagues } from '@/composables/useResultsLeagues'
import { useTrackedLeagues } from '@/composables/useTrackedLeagues'
import { parseApiDate } from '@/utils/format'
import {
  fixturesShellContext,
  readFixturesLeagueFilter,
  writeFixturesLeagueFilter,
  type FixturesRouteName,
} from '@/utils/fixturesLeagueFilter'
import {
  homeDayCountLabel,
  isHomeFixtureVisible,
  isPredictionsFixtureVisible,
  isScheduleFutureDay,
  predictionsDayCountLabel,
  resultsDayCountLabel,
  scheduleDayCountLabel,
  todayDate,
  yesterdayDate,
} from '@/utils/homeDateStrip'
import { leagueLabel } from '@/utils/leagueNames'
import { filterByTeamQuery, teamSearchEmptyHint } from '@/utils/teamSearch'
import { hasOddsMarkets } from '@/utils/oddsDisplay'

const FIXTURES_ROUTE_NAMES = new Set<string>(['home', 'predictions', 'results'])

const selectedDay = ref(yesterdayDate())
const prematchSelectedLeagueId = ref<number | null>(null)
const resultsSelectedLeagueId = ref<number | null>(null)
const teamSearch = ref('')
const siderCollapsed = ref(false)
const leagueDrawerShow = ref(false)
const filterConfirming = ref(false)

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
  } = useResultsLeagues()

  const pageName = computed(
    () => route.name as FixturesRouteName | undefined,
  )
  const isResultsPage = computed(() => pageName.value === 'results')
  const isScheduleFutureDayRef = computed(
    () => isResultsPage.value && isScheduleFutureDay(selectedDay.value, todayDate()),
  )
  const homeDay = computed(() => todayDate())
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
    const day = homeDay.value
    const today = todayDate()
    if (pageName.value === 'predictions') {
      return allFixtures.value.filter(
        (f) => tracked.has(f.league_id) && isPredictionsFixtureVisible(f.status),
      )
    }
    return allFixtures.value.filter(
      (f) =>
        tracked.has(f.league_id) &&
        isHomeFixtureVisible(f.status, day, today),
    )
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
    isResultsPage.value ? resultsTrackedIds.value : prematchTrackedIds.value,
  )
  const shellFilterOptions = computed(() =>
    isResultsPage.value ? resultsFilterOptions.value : prematchFilterOptions.value,
  )
  const shellFilterActive = computed(() =>
    isResultsPage.value ? resultsFilterActive.value : prematchFilterActive.value,
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
    if (pageName.value === 'predictions') return '预测'
    if (pageName.value === 'results') return '赛程'
    return '即时'
  })

  const breadcrumbFilter = computed(() =>
    selectedLeague.value ? leagueLabel(selectedLeague.value.league_name) : '全部',
  )

  function leagueFiltered<T extends { league_id: number }>(list: T[]) {
    if (selectedLeagueId.value == null) return list
    return list.filter((f) => f.league_id === selectedLeagueId.value)
  }

  function sortFixtures<T extends { fixture_date: string }>(list: T[]) {
    return list
      .slice()
      .sort(
        (a, b) =>
          parseApiDate(a.fixture_date).getTime() -
          parseApiDate(b.fixture_date).getTime(),
      )
  }

  const homeDayFixtures = computed(() =>
    allFixtures.value.filter(
      (f) =>
        prematchTrackedIdSet.value.has(f.league_id) &&
        isHomeFixtureVisible(f.status, homeDay.value, todayDate()),
    ),
  )

  const predictionsDayFixtures = computed(() =>
    allFixtures.value.filter(
      (f) =>
        prematchTrackedIdSet.value.has(f.league_id) &&
        isPredictionsFixtureVisible(f.status),
    ),
  )

  const homeDisplayedFixtures = computed(() =>
    filterByTeamQuery(
      sortFixtures(leagueFiltered(homeDayFixtures.value)),
      teamSearch.value,
    ),
  )

  const predictionsDisplayedFixtures = computed(() =>
    filterByTeamQuery(
      sortFixtures(leagueFiltered(predictionsDayFixtures.value)),
      teamSearch.value,
    ),
  )

  const dayCountLabel = computed(() => {
    if (isResultsPage.value) {
      const count =
        selectedLeagueId.value == null
          ? shellTotalCount.value
          : shellCountByLeague.value.get(selectedLeagueId.value) || 0
      return isScheduleFutureDayRef.value
        ? scheduleDayCountLabel(count)
        : resultsDayCountLabel(count)
    }
    const list = leagueFiltered(prematchVisibleFixtures.value)
    const count = filterByTeamQuery(sortFixtures(list), teamSearch.value).length
    if (pageName.value === 'predictions') return predictionsDayCountLabel(count)
    return homeDayCountLabel('today', count)
  })

  const homeEmptyText = computed(() => {
    if (error.value) return ''
    const day = homeDay.value
    if (
      isDayAutoSynced(day) &&
      !allFixtures.value.length &&
      !contentLoading.value
    ) {
      return `${day} 当日没有比赛数据`
    }
    if (!prematchFilterOptions.value.length && !homeDayFixtures.value.length) {
      return '暂无匹配联赛，正在拉取配置联赛赛程…'
    }
    if (!prematchTrackedIds.value.length) {
      return '请先在「筛选」中勾选要关注的联赛'
    }
    if (!homeDisplayedFixtures.value.length && !teamSearch.value.trim()) {
      return `${day} 暂无当日赛事`
    }
    const teamHint = teamSearchEmptyHint(teamSearch.value)
    if (teamHint && sortFixtures(leagueFiltered(homeDayFixtures.value)).length) {
      return teamHint
    }
    if (selectedLeagueId.value == null) {
      return `${day} 勾选联赛暂无当日赛事`
    }
    const name = leagueLabel(selectedLeague.value?.league_name) || '该联赛'
    return `${day} 暂无${name}当日赛事`
  })

  const predictionsEmptyText = computed(() => {
    if (error.value) return ''
    const day = homeDay.value
    if (
      isDayAutoSynced(day) &&
      !allFixtures.value.length &&
      !contentLoading.value
    ) {
      return `${day} 当日没有比赛数据`
    }
    if (!prematchTrackedIds.value.length) return '请先在「筛选」中勾选联赛'
    if (!predictionsDisplayedFixtures.value.length && !teamSearch.value.trim()) {
      return `${day} 暂无未完赛预测`
    }
    const teamHint = teamSearchEmptyHint(teamSearch.value)
    if (teamHint && sortFixtures(leagueFiltered(predictionsDayFixtures.value)).length) {
      return teamHint
    }
    return `${day} 暂无未完赛预测`
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

  function leagueIdsForSync(): number[] | undefined {
    return prematchTrackedIds.value.length ? prematchTrackedIds.value : undefined
  }

  function prematchMissingOddsCount(): number {
    const day = homeDay.value
    const today = todayDate()
    return allFixtures.value.filter(
      (f) =>
        prematchTrackedIdSet.value.has(f.league_id) &&
        isHomeFixtureVisible(f.status, day, today) &&
        f.status.toLowerCase() === 'pending' &&
        !hasOddsMarkets(f.odds_snippet),
    ).length
  }

  function syncCalendarDay() {
    return isResultsPage.value ? selectedDay.value : homeDay.value
  }

  function onSyncSettled(_ok: boolean, day?: string) {
    const syncDay = day ?? syncCalendarDay()
    markDayAutoSynced(syncDay)
    const tasks: Promise<unknown>[] = [loadDayLocal(true)]
    if (!isResultsPage.value) {
      tasks.unshift(loadFilterOptions({ date: homeDay.value, discover: true }))
    }
    void Promise.all(tasks)
  }

  function startBackgroundSync(
    leagueIds: number[] | undefined,
    opts: SyncFixturesOptions,
    day?: string,
  ) {
    const syncDay = day ?? opts.date ?? syncCalendarDay()
    enqueueBackgroundSync(
      {
        days: opts.days ?? 1,
        date: opts.date ?? syncDay,
        includeResults: opts.includeResults ?? true,
        includeOdds: opts.includeOdds ?? true,
        oddsRefreshExisting: opts.oddsRefreshExisting ?? true,
        oddsBudget: opts.oddsBudget,
        leagueIds,
        oddsOnly: opts.oddsOnly ?? false,
      },
      (ok) => onSyncSettled(ok, syncDay),
    )
  }

  function gapFillOddsIfNeeded(day = homeDay.value) {
    const missing = prematchMissingOddsCount()
    if (missing <= 0 || !shouldGapFillOdds(day)) return
    markOddsGapFillTried(day)
    startBackgroundSync(leagueIdsForSync(), {
      date: day,
      days: 1,
      includeResults: false,
      includeOdds: true,
      oddsRefreshExisting: false,
      oddsBudget: Math.min(Math.max(missing, 1), 100),
      oddsOnly: true,
    }, day)
  }

  async function loadDayLocal(force = false) {
    const day = isResultsPage.value ? selectedDay.value : homeDay.value
    try {
      await loadHomeFixtures({ force, date: day, days: 1 })
      if (!isResultsPage.value) syncLeagueFromRoute()
    } catch {
      // error already set in composable
    }
  }

  async function refreshDayData() {
    const day = homeDay.value
    await loadDayLocal(false)
    const leagueIds = leagueIdsForSync()
    const hasLocal = allFixtures.value.length > 0

    if (shouldAutoSyncDay(day, hasLocal)) {
      startBackgroundSync(leagueIds, { date: day, days: 1 }, day)
      return
    }

    gapFillOddsIfNeeded(day)
  }

  function forceRefreshDay() {
    const day = homeDay.value
    clearOddsGapFillTried(day)
    startBackgroundSync(leagueIdsForSync(), {
      date: day,
      days: 1,
      includeResults: true,
      includeOdds: true,
      oddsRefreshExisting: true,
    }, day)
  }

  async function reloadPrematchDay() {
    try {
      await loadFilterOptions({ date: homeDay.value, discover: true })
    } catch {
      if (filterOptionsError.value) message.warning(filterOptionsError.value)
    }
    await refreshDayData()
  }

  async function confirmFilter(ids: number[]) {
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
    const needFetch = allowed.filter((id) => {
      const opt = prematchFilterOptionById.value.get(id)
      return !!opt && !opt.locally_loaded
    })
    if (needFetch.length) {
      filterConfirming.value = true
      enqueueBackgroundSync(
        {
          days: 1,
          date: homeDay.value,
          includeResults: false,
          includeOdds: true,
          oddsRefreshExisting: false,
          oddsBudget: 30,
          leagueIds: needFetch,
        },
        (ok) => {
          filterConfirming.value = false
          onSyncSettled(ok, homeDay.value)
        },
      )
    } else {
      await loadDayLocal(false)
      gapFillOddsIfNeeded()
    }
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

    watch(prematchTrackedIds, () => {
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
        const prematch = name === 'home' || name === 'predictions'
        if (prematch && prev === 'results') {
          void reloadPrematchDay()
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
    filterConfirming,
    contentLoading,
    error,
    shellTrackedIds,
    shellFilterOptions,
    shellFilterActive,
    shellMenuLeagues,
    shellCountByLeague,
    shellTotalCount,
    selectedLeague,
    breadcrumbRoot,
    breadcrumbFilter,
    dayCountLabel,
    homeDisplayedFixtures,
    predictionsDisplayedFixtures,
    homeEmptyText,
    predictionsEmptyText,
    loadDayLocal,
    forceRefreshDay,
    reloadPrematchDay,
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
