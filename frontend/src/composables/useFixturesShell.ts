import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'

import { syncFixtures } from '@/api/fixtures'
import type { LeagueSummaryResponse } from '@/api/types'
import { markDayAutoSynced, isDayAutoSynced, shouldAutoSyncDay } from '@/composables/useDayAutoSync'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
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
  homeDayKind,
  homeDayStatusHint,
  isHomeFixtureVisible,
  isPredictionsFixtureVisible,
  predictionsDayCountLabel,
  resultsDayCountLabel,
  todayDate,
} from '@/utils/homeDateStrip'
import { leagueLabel } from '@/utils/leagueNames'
import { filterByTeamQuery, teamSearchEmptyHint } from '@/utils/teamSearch'

const FIXTURES_ROUTE_NAMES = new Set<string>(['home', 'predictions', 'results'])

const selectedDay = ref(todayDate())
const prematchSelectedLeagueId = ref<number | null>(null)
const resultsSelectedLeagueId = ref<number | null>(null)
const teamSearch = ref('')
const siderCollapsed = ref(false)
const leagueDrawerShow = ref(false)
const syncing = ref(false)

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
    isResultsPage.value ? resultsLoading.value : prematchLoading.value || syncing.value,
  )

  const shellLoading = computed(() =>
    isResultsPage.value ? resultsLoading.value : prematchLoading.value,
  )

  const prematchTrackedIdSet = computed(() => new Set(prematchTrackedIds.value))
  const prematchFilterOptions = computed(() => allFilterOptions())
  const prematchFilterOptionById = computed(
    () => new Map(prematchFilterOptions.value.map((o) => [o.league_id, o])),
  )

  const selectedDayKind = computed(() =>
    homeDayKind(selectedDay.value, todayDate()),
  )

  const prematchVisibleFixtures = computed(() => {
    const tracked = prematchTrackedIdSet.value
    const day = selectedDay.value
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
    if (pageName.value === 'results') return '赛果'
    return '赛前赛事'
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
        isHomeFixtureVisible(f.status, selectedDay.value, todayDate()),
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
      return resultsDayCountLabel(count)
    }
    const list = leagueFiltered(prematchVisibleFixtures.value)
    const count = filterByTeamQuery(sortFixtures(list), teamSearch.value).length
    if (pageName.value === 'predictions') return predictionsDayCountLabel(count)
    return homeDayCountLabel(selectedDayKind.value, count)
  })

  const homeEmptyText = computed(() => {
    if (error.value) return ''
    const statusHint = homeDayStatusHint(selectedDayKind.value)
    if (
      isDayAutoSynced(selectedDay.value) &&
      !allFixtures.value.length &&
      !contentLoading.value
    ) {
      return `${selectedDay.value} 当日没有比赛数据`
    }
    if (!prematchFilterOptions.value.length && !homeDayFixtures.value.length) {
      return '暂无匹配联赛，正在拉取配置联赛赛程…'
    }
    if (!prematchTrackedIds.value.length) {
      return '请先在「筛选」中勾选要关注的联赛'
    }
    if (!homeDisplayedFixtures.value.length && !teamSearch.value.trim()) {
      return `${selectedDay.value} 暂无${statusHint}赛事`
    }
    const teamHint = teamSearchEmptyHint(teamSearch.value)
    if (teamHint && sortFixtures(leagueFiltered(homeDayFixtures.value)).length) {
      return teamHint
    }
    if (selectedLeagueId.value == null) {
      return `${selectedDay.value} 勾选联赛暂无${statusHint}赛事`
    }
    const name = leagueLabel(selectedLeague.value?.league_name) || '该联赛'
    return `${selectedDay.value} 暂无${name}${statusHint}赛事`
  })

  const predictionsEmptyText = computed(() => {
    if (error.value) return ''
    if (
      isDayAutoSynced(selectedDay.value) &&
      !allFixtures.value.length &&
      !contentLoading.value
    ) {
      return `${selectedDay.value} 当日没有比赛数据`
    }
    if (!prematchTrackedIds.value.length) return '请先在「筛选」中勾选联赛'
    if (!predictionsDisplayedFixtures.value.length && !teamSearch.value.trim()) {
      return `${selectedDay.value} 暂无未完赛预测`
    }
    const teamHint = teamSearchEmptyHint(teamSearch.value)
    if (teamHint && sortFixtures(leagueFiltered(predictionsDayFixtures.value)).length) {
      return teamHint
    }
    return `${selectedDay.value} 暂无未完赛预测`
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

  async function loadDayLocal(force = false) {
    try {
      await loadHomeFixtures({ force, date: selectedDay.value, days: 1 })
      if (!isResultsPage.value) syncLeagueFromRoute()
    } catch {
      // error already set in composable
    }
  }

  async function runSync(
    leagueIds: number[] | undefined,
    opts?: {
      days?: number
      date?: string
      includeResults?: boolean
      includeOdds?: boolean
      oddsRefreshExisting?: boolean
      oddsBudget?: number
      rediscoverLeagues?: boolean
    },
  ) {
    syncing.value = true
    try {
      await syncFixtures({
        days: opts?.days ?? 1,
        date: opts?.date ?? selectedDay.value,
        includeResults: opts?.includeResults ?? true,
        includeOdds: opts?.includeOdds ?? true,
        oddsRefreshExisting: opts?.oddsRefreshExisting ?? true,
        oddsBudget: opts?.oddsBudget,
        leagueIds,
      })
      markDayAutoSynced(opts?.date ?? selectedDay.value)
      await Promise.all([
        loadFilterOptions({
          date: selectedDay.value,
          discover: opts?.rediscoverLeagues ?? true,
        }),
        loadDayLocal(true),
      ])
      return true
    } catch (err) {
      message.error(err instanceof Error ? err.message : '获取失败')
      markDayAutoSynced(opts?.date ?? selectedDay.value)
      await loadDayLocal(true)
      return false
    } finally {
      syncing.value = false
    }
  }

  async function refreshDayData() {
    const day = selectedDay.value
    await loadDayLocal(false)
    if (!shouldAutoSyncDay(day, allFixtures.value.length > 0)) return
    await runSync(leagueIdsForSync(), { date: day, days: 1 })
  }

  async function reloadPrematchDay() {
    try {
      await loadFilterOptions({ date: selectedDay.value, discover: true })
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
      await runSync(needFetch, {
        days: 1,
        date: selectedDay.value,
        includeResults: false,
        includeOdds: true,
        oddsRefreshExisting: false,
        oddsBudget: 30,
        rediscoverLeagues: false,
      })
    } else {
      await loadDayLocal(false)
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

  return {
    selectedDay,
    selectedLeagueId,
    teamSearch,
    siderCollapsed,
    leagueDrawerShow,
    syncing,
    contentLoading,
    shellLoading,
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
    reloadPrematchDay,
    confirmFilter,
    selectLeague,
    syncLeagueFromRoute,
    isResultsPage,
  }
}

export function initFixturesShellOnMount(isResults: boolean) {
  const { syncLeagueFromRoute, reloadPrematchDay } = useFixturesShell()
  syncLeagueFromRoute()
  if (!isResults) void reloadPrematchDay()
}

export function activateFixturesShell() {
  const { syncLeagueFromRoute } = useFixturesShell()
  syncLeagueFromRoute()
}
