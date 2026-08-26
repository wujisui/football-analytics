<script setup lang="ts">
import {computed, defineAsyncComponent, onActivated, ref, watch} from 'vue'
import {useRoute, useRouter} from 'vue-router'

import {
  fetchResults,
  fetchResultsHistory,
  fetchTodayFixtures,
  type ResultFixture,
  type ResultsAccuracy,
} from '@/api/fixtures'
import AccuracyMetricsGrid from '@/views/Results/components/AccuracyMetricsGrid.vue'
import ChartWindowControls, {
  DEFAULT_CHART_WINDOW_DAYS,
} from '@/views/Results/components/ChartWindowControls.vue'
import FixtureList from '@/components/FixtureList.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import PullToRefresh from '@/components/PullToRefresh.vue'
import HomeDateStrip from '@/layouts/components/HomeDateStrip.vue'
import ResultsListToolbar from '@/views/Results/components/ResultsListToolbar.vue'
import ResultsFixtureVirtualList from '@/views/Results/components/ResultsFixtureVirtualList.vue'
import {
  hasSessionShellDay,
  useFixturesShell,
} from '@/layouts/composables/useFixturesShell'
import {useHorizontalSwipe} from '@/composables/useHorizontalSwipe'
import {useIsPhone} from '@/composables/useMediaQuery'
import {useMarkedFixture} from '@/composables/useMarkedFixture'
import {useScrollRestore} from '@/composables/useScrollRestore'
import {useFavoriteFixtures} from '@/composables/useFavoriteFixtures'
import {
  cacheResultsHistory,
  consumeResultsSettlementDirty,
  invalidateCachedResultsDay,
  loadResultsFilterOptions,
  publishResultsFixtures,
  publishScheduleFixtures,
  restoreCachedResultsDay,
  setResultsLoading,
  useResultsLeagues,
} from '@/composables/useResultsLeagues'
import {
  beginScheduleFilterOverride,
  endScheduleFilterOverride,
} from '@/composables/useTrackedLeagues'
import {fixtureDetailRoute} from '@/utils/detailNav'
import {scheduleTodayDate, todayDate, yesterdayDate} from '@/utils/homeDateStrip'
import {sortFixturesFavoritesFirst} from '@/utils/fixtureSort'
import {filterByTeamQuery, teamSearchEmptyHint} from '@/utils/teamSearch'
import {
  readResultsPageState,
  writeResultsPageState,
  RESULTS_PHONE_TABS,
  type ResultsHitKey,
  type ResultsPhoneTab,
} from '@/utils/resultsPageState'

defineOptions({name: 'Results'})

/** echarts is heavy; keep it out of the first-paint bundle. */
const AccuracyHistoryChart = defineAsyncComponent(
    () => import('@/views/Results/components/AccuracyHistoryChart.vue'),
)

const HIT_FIELD: Record<ResultsHitKey, keyof ResultFixture> = {
  result: 'result_hit',
  auto_pick: 'auto_pick_hit',
  score: 'score_hit',
  ou: 'ou_hit',
  btts: 'btts_hit',
  handicap: 'handicap_hit',
}

const isPhone = useIsPhone()

/** Phone results-day panes; default list so fixtures stay primary. */
const phoneResultsTab = ref<ResultsPhoneTab>('list')
const showDayStatsModal = ref(false)
const localRefreshing = ref(false)

function onPhoneResultsTabChange(name: string) {
  if ((RESULTS_PHONE_TABS as string[]).includes(name)) {
    phoneResultsTab.value = name as ResultsPhoneTab
  }
}

function shiftPhoneResultsTab(delta: number) {
  const i = RESULTS_PHONE_TABS.indexOf(phoneResultsTab.value)
  if (i < 0) return
  const next = RESULTS_PHONE_TABS[i + delta]
  if (next) phoneResultsTab.value = next
}

const phoneSwipeHandlers = useHorizontalSwipe({
  enabled: isPhone,
  onSwipeLeft: () => shiftPhoneResultsTab(1),
  onSwipeRight: () => shiftPhoneResultsTab(-1),
})

const route = useRoute()
const router = useRouter()
const {favoriteIds, dailyPickIds: autoFavoriteIds} = useFavoriteFixtures()
const {
  resultsTrackedIds,
  resultsFixtures,
  scheduleFixtures,
  resultsLoadedDay,
  resultsHistory,
  resultsDataRevision,
} = useResultsLeagues()
const {
  selectedDay,
  selectedLeagueId,
  teamSearch,
  contentLoading: shellContentLoading,
  isScheduleFutureDay,
  resultsFilterRevision,
  resultsFilterRevisionDay,
  loadFilterOptions,
  syncFutureScheduleSelection,
  resultsDayFixtureCount,
  shellFilterOptions,
  shellTrackedIds,
  shellFilterActive,
  confirmFilter,
} = useFixturesShell()

const desktopListShellRef = ref<HTMLElement | null>(null)
const phoneListShellRef = ref<HTMLElement | null>(null)

/** Desktop sider keeps the original compact 12px list inset.
 *  Phone: outer tabs wrap already pads — keep list flush to avoid double inset. */
const resultsListItemsStyle = computed(() =>
  isPhone.value
    ? undefined
    : {
        paddingLeft: '12px',
        paddingRight: '12px',
        boxSizing: 'border-box',
      },
)

const desktopListScroll = useScrollRestore('results-list-desktop', desktopListShellRef)
const phoneListScroll = useScrollRestore('results-list-phone', phoneListShellRef)

const fixtures = resultsFixtures
const history = resultsHistory
const loading = ref(false)
const historyLoading = ref(false)
const error = ref('')
/** Click a hit tag on a card → keep fixtures that hit that market; click again to clear. */
const filterHitKey = ref<ResultsHitKey | null>(null)
const { markedFixtureId, toggleMarked, clearMarked, retainIfPresent } =
  useMarkedFixture()

const contentLoading = computed(
    () => loading.value || shellContentLoading.value,
)

const isResultsDay = computed(
    () => !isScheduleFutureDay.value,
)

const trackedIdSet = computed(() => new Set(resultsTrackedIds.value))

const scheduleDisplayedFixtures = computed(() => {
  let list = scheduleFixtures.value.filter((f) => trackedIdSet.value.has(f.league_id))
  if (selectedLeagueId.value != null) {
    list = list.filter((f) => f.league_id === selectedLeagueId.value)
  }
  return sortFixturesFavoritesFirst(
      filterByTeamQuery(list, teamSearch.value),
      favoriteIds.value,
      autoFavoriteIds.value,
  )
})

const leagueScopedFixtures = computed(() => {
  let list = fixtures.value.filter((fx) => trackedIdSet.value.has(fx.league_id))
  if (selectedLeagueId.value != null) {
    list = list.filter((fx) => fx.league_id === selectedLeagueId.value)
  }
  return list
})

const listedDailyPickIds = computed(() => {
  const ids = new Set(autoFavoriteIds.value)
  for (const fx of fixtures.value) {
    if (fx.auto_pick_market) ids.add(fx.fixture_id)
  }
  return ids
})

const listedFixtures = computed(() => {
  let list = leagueScopedFixtures.value
  const hitKey = filterHitKey.value
  if (hitKey) {
    const field = HIT_FIELD[hitKey]
    list = list.filter((fx) => fx[field] === true)
  }
  return sortFixturesFavoritesFirst(
      filterByTeamQuery(list, teamSearch.value),
      favoriteIds.value,
      listedDailyPickIds.value,
  )
})

const listedFinishedCount = computed(
  () =>
    listedFixtures.value.filter(
      (fx) => (fx.status || '').toLowerCase() === 'finished',
    ).length,
)

const listedVirtualRows = computed(() =>
  listedFixtures.value.map((fixture) => ({
    key: fixture.fixture_id,
    fixture,
  })) as Record<string, unknown>[],
)

watch(
  () => listedFixtures.value.map((fx) => fx.fixture_id),
  (ids) => retainIfPresent(ids),
)

function onFilterHit(key: ResultsHitKey) {
  filterHitKey.value = filterHitKey.value === key ? null : key
}

/** Mirrors backend ``summarize_accuracy``; grades any non-null hit flag. */
function summarizeFiltered(list: ResultFixture[]): ResultsAccuracy {
  const rows = list.map((fx) => ({
    has_prediction: !!fx.has_prediction,
    // Unsettled rows (feed still live) carry provisional scores — never graded.
    evaluable:
        (fx.status || '').toLowerCase() === 'finished' &&
        fx.home_goals != null &&
        fx.away_goals != null,
    result_hit: fx.result_hit ?? null,
    auto_pick_hit: fx.auto_pick_hit ?? null,
    score_hit: fx.score_hit ?? null,
    ou_hit: fx.ou_hit ?? null,
    btts_hit: fx.btts_hit ?? null,
    handicap_hit: fx.handicap_hit ?? null,
  }))
  const rate = (
      key:
          | 'result_hit'
          | 'auto_pick_hit'
          | 'score_hit'
          | 'ou_hit'
          | 'btts_hit'
          | 'handicap_hit',
  ) => {
    const evalRows = rows.filter((r) => r[key] !== null && r[key] !== undefined)
    const hits = evalRows.filter((r) => r[key] === true).length
    const total = evalRows.length
    return {
      hits,
      total,
      rate: total > 0 ? hits / total : null,
    }
  }
  return {
    result: rate('result_hit'),
    auto_pick: rate('auto_pick_hit'),
    score: rate('score_hit'),
    ou: rate('ou_hit'),
    btts: rate('btts_hit'),
    handicap: rate('handicap_hit'),
    fixtures_with_prediction: rows.filter((r) => r.has_prediction).length,
    fixtures_finished: rows.filter((r) => r.evaluable).length,
  }
}

/** Day panel follows the league filter/selection. */
const displayAccuracy = computed(() =>
    summarizeFiltered(leagueScopedFixtures.value),
)

const emptyText = computed(() => {
  if (!selectedDay.value) return '请选择日期'
  const teamHint = teamSearchEmptyHint(teamSearch.value)
  if (teamHint && leagueScopedFixtures.value.length) return teamHint
  if (fixtures.value.length && !listedFixtures.value.length) {
    return filterHitKey.value
      ? '当前命中筛选下无场次，可再点同一标签取消'
      : '当前筛选下无场次，可调整联赛筛选'
  }
  return `${selectedDay.value} 暂无赛果场次，可刷新页面重试`
})

const scheduleEmptyText = computed(() => {
  if (!selectedDay.value) return '请选择日期'
  const teamHint = teamSearchEmptyHint(teamSearch.value)
  if (teamHint && scheduleFixtures.value.length) return teamHint
  return `${selectedDay.value} 暂无未开赛赛程，可刷新页面重试`
})

const dayAccuracyHeaderExtra = computed(() => {
  const count = displayAccuracy.value?.fixtures_with_prediction ?? 0
  const day = selectedDay.value
  if (!day) return count ? `${count} 场` : '—'
  return `${count} 场 · ${day}`
})

const historyStartDate = computed(() => history.value?.start_date || '—')

/** Align with 当日统计 header-extra: count · start date. */
const historyHeaderExtra = computed(() => {
  if (!history.value) return '—'
  const count = history.value.overall?.fixtures_with_prediction ?? 0
  if (!count) return '暂无已预测完场'
  const start = historyStartDate.value
  return start !== '—' ? `${count} 场 · ${start}` : `${count} 场`
})

const chartSeries = computed(() => history.value?.series ?? [])

const hasChartData = computed(
    () => chartSeries.value.some((p) => p.fixtures_with_prediction > 0),
)

const chartWindowDays = ref(DEFAULT_CHART_WINDOW_DAYS)

/** Chart point click: jump list + 当日统计 to that sample day (full history picker). */
function selectChartDay(day: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return
  if (day > todayDate()) return
  if (day === selectedDay.value) return
  filterHitKey.value = null
  selectedDay.value = day
  if (isPhone.value) phoneResultsTab.value = 'list'
}

function goDetail(fixtureId: number) {
  void router.push(
      fixtureDetailRoute(fixtureId, {
        from: 'results',
        tab: 'prediction',
        date: selectedDay.value,
      }),
  )
}

function applySavedFiltersIfAny() {
  const saved = readResultsPageState()
  if (!saved || saved.date !== selectedDay.value) return
  phoneResultsTab.value = saved.phoneTab
}

watch([selectedDay, phoneResultsTab], () => {
  writeResultsPageState({
    date: selectedDay.value,
    phoneTab: phoneResultsTab.value,
  })
})

async function loadDayResults() {
  if (!selectedDay.value) {
    fixtures.value = []
    publishResultsFixtures([], selectedDay.value)
    return
  }
  loading.value = true
  setResultsLoading(true)
  error.value = ''
  try {
    await loadResultsFilterOptions({
      date: selectedDay.value,
      schedule: false,
    })
    const leagueIds = [...resultsTrackedIds.value]
    if (!leagueIds.length) {
      publishResultsFixtures([], selectedDay.value)
      return
    }
    const data = await fetchResults(selectedDay.value, {leagueIds})
    publishResultsFixtures(data.fixtures, selectedDay.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取失败'
    publishResultsFixtures([], selectedDay.value)
    invalidateCachedResultsDay(selectedDay.value, false)
  } finally {
    loading.value = false
    setResultsLoading(false)
  }
}

async function loadHistory(force = false) {
  if (!force && history.value) return
  historyLoading.value = true
  try {
    // UTC schedule day — same clock as backend utc_today / series dates.
    const cutoff = scheduleTodayDate()
    cacheResultsHistory(
        await fetchResultsHistory({days: 0, endDate: cutoff}),
    )
  } catch {
    if (!history.value) cacheResultsHistory(null)
  } finally {
    historyLoading.value = false
  }
}

async function loadScheduleDay() {
  if (!selectedDay.value) {
    publishScheduleFixtures([], selectedDay.value)
    return
  }
  loading.value = true
  setResultsLoading(true)
  error.value = ''
  // Future-day catalog overrides shared prematch filter; freeze calculator first.
  beginScheduleFilterOverride()
  try {
    await loadFilterOptions({date: selectedDay.value, scope: 'prematch'})
    await loadResultsFilterOptions({
      date: selectedDay.value,
      schedule: true,
    })
    syncFutureScheduleSelection()
    const leagueIds = [...resultsTrackedIds.value]
    if (!leagueIds.length) {
      publishScheduleFixtures([], selectedDay.value)
      return
    }
    const data = await fetchTodayFixtures({
      date: selectedDay.value,
      days: 1,
      leagueIds,
    })
    publishScheduleFixtures(data.fixtures, selectedDay.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取失败'
    publishScheduleFixtures([], selectedDay.value)
    invalidateCachedResultsDay(selectedDay.value, true)
  } finally {
    loading.value = false
    setResultsLoading(false)
  }
}

async function loadSelectedDay(force = false) {
  if (!selectedDay.value) {
    fixtures.value = []
    publishResultsFixtures([], selectedDay.value)
    publishScheduleFixtures([], selectedDay.value)
    return
  }

  if (
      !force &&
      restoreCachedResultsDay(selectedDay.value, isScheduleFutureDay.value)
  ) {
    syncFutureScheduleSelection()
    error.value = ''
    return
  }

  if (isScheduleFutureDay.value) {
    await loadScheduleDay()
    return
  }

  await loadDayResults()
}

async function refreshLocalResults() {
  if (localRefreshing.value) return
  localRefreshing.value = true
  try {
    await loadSelectedDay(true)
    if (!isScheduleFutureDay.value) await loadHistory(true)
  } finally {
    localRefreshing.value = false
  }
}

watch(resultsDataRevision, () => {
  // Prematch rows adapt the lean client-side; only settled days need a re-read.
  if (isScheduleFutureDay.value) return
  // useResultsLeagues already dropped the cached hits; re-settle the open day.
  void loadSelectedDay(true)
  void loadHistory(true)
})

watch(isScheduleFutureDay, (future, wasFuture) => {
  if (wasFuture && !future) endScheduleFilterOverride()
})

watch(selectedDay, () => {
  if (route.name !== 'results') return
  filterHitKey.value = null
  clearMarked()
  desktopListScroll.reset()
  phoneListScroll.reset()
  void loadSelectedDay()
})

watch(resultsFilterRevision, () => {
  if (
      route.name !== 'results'
      || resultsFilterRevisionDay.value !== selectedDay.value
  ) {
    return
  }
  // A confirmed league filter reloads the selected local day.
  void loadSelectedDay(true)
})

let visited = false
onActivated(() => {
  /**
   * keep-alive 下首次挂载也会触发 onActivated，勿再挂 onMounted 拉数，
   * 否则 filter-options / fixtures/results 会各打两次。
   */
  let dayChanged = false
  if (!visited) {
    const qDate = route.query.date
    if (typeof qDate === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(qDate)) {
      if (qDate !== selectedDay.value) {
        selectedDay.value = qDate
        dayChanged = true
      }
    } else if (!hasSessionShellDay && selectedDay.value !== yesterdayDate()) {
      selectedDay.value = yesterdayDate()
      dayChanged = true
    }
  }

  if (isScheduleFutureDay.value) {
    if (!visited) {
      visited = true
      // dayChanged → watch(selectedDay) already queued loadSelectedDay.
      if (!dayChanged && resultsLoadedDay.value !== selectedDay.value) {
        void loadSelectedDay()
      }
      return
    }
    if (resultsLoadedDay.value !== selectedDay.value) {
      void loadSelectedDay()
    }
    return
  }

  applySavedFiltersIfAny()

  if (!visited) {
    visited = true
    if (!dayChanged && resultsLoadedDay.value !== selectedDay.value) {
      void loadSelectedDay()
    }
    void loadHistory()
    return
  }

  // Detail may have written FT score into the list cache without hit flags.
  // Force a local reload so evaluate_fixture_prediction settles recommendations.
  if (consumeResultsSettlementDirty(selectedDay.value)) {
    void loadSelectedDay(true)
    void loadHistory(true)
    return
  }
  if (resultsLoadedDay.value !== selectedDay.value) {
    void loadSelectedDay()
  }
})
</script>

<template>
  <n-layout
      class="results-layout"
      :has-sider="!isPhone && isResultsDay"
      content-style="display: flex; flex-direction: column; height: 100%; min-height: 0;"
  >
    <!-- Phone: results day as swipeable tabs -->
    <div
        v-if="isPhone && isResultsDay"
        class="phone-results-tabs-wrap"
        @touchstart.passive="phoneSwipeHandlers.onTouchStart"
        @touchmove.passive="phoneSwipeHandlers.onTouchMove"
        @touchend="phoneSwipeHandlers.onTouchEnd"
        @touchcancel="phoneSwipeHandlers.onTouchCancel"
    >
      <n-tabs
          :value="phoneResultsTab"
          type="line"
          size="small"
          :animated="false"
          class="phone-results-tabs"
          @update:value="onPhoneResultsTabChange"
      >
        <n-tab-pane name="list" display-directive="if">
          <template #tab>
            <n-badge :value="resultsDayFixtureCount" :max="999" :offset="[10, 8]">
              赛果
            </n-badge>
          </template>
          <div class="phone-tab-pane phone-list-pane">
            <div class="phone-list-toolbar">
              <ResultsListToolbar
                  v-model:team-search="teamSearch"
                  :filter-options="shellFilterOptions"
                  :tracked-ids="shellTrackedIds"
                  :filter-active="shellFilterActive"
                  :list-count="listedFixtures.length"
                  :finished-count="listedFinishedCount"
                  show-day-stats
                  @confirm-filter="confirmFilter"
                  @open-day-stats="showDayStatsModal = true"
              />
            </div>
            <n-alert
                v-if="error"
                type="error"
                title="获取失败"
                class="phone-list-alert"
            >
              <n-space align="center" :size="12">
                <span>{{ error }}</span>
                <n-button size="small" type="primary" @click="loadDayResults()">重试</n-button>
              </n-space>
            </n-alert>
            <div ref="phoneListShellRef" class="list-shell phone">
              <PullToRefresh
                  :shell="phoneListShellRef"
                  :refreshing="localRefreshing"
                  @refresh="refreshLocalResults"
              />
              <ResultsFixtureVirtualList
                  :empty="!loading && !listedFixtures.length"
                  :empty-description="emptyText"
                  :items="listedVirtualRows"
                  :content-loading="contentLoading"
                  :filter-hit-key="filterHitKey"
                  :padding-top="8"
                  :padding-bottom="16"
                  :items-style="resultsListItemsStyle"
                  :marked-fixture-id="markedFixtureId"
                  @open-detail="goDetail"
                  @filter-hit="onFilterHit"
                  @toggle-select="toggleMarked"
              />
              <ListBackTop
                  :shell="phoneListShellRef"
                  :content-key="listedFixtures.length"
                  :right="12"
                  :bottom="12"
              />
            </div>
          </div>
        </n-tab-pane>

        <!-- Destroy chart when leaving — echarts+autoresize otherwise keeps GPU warm. -->
        <n-tab-pane name="history" tab="历史统计" display-directive="if">
          <div class="phone-tab-pane">
            <n-scrollbar style="height: 100%;" trigger="hover">
              <div class="phone-stat-pane">
                <n-spin :show="historyLoading">
                  <AccuracyMetricsGrid :metrics="history?.overall" />
                </n-spin>
                <n-divider/>
                <div class="phone-history-chart-block" data-no-tab-swipe>
                  <div class="phone-chart-toolbar">
                    <n-ellipsis class="chart-title-line">
                      走势图 · 起始 {{ historyStartDate }}
                    </n-ellipsis>
                    <ChartWindowControls
                      v-model="chartWindowDays"
                      select-width="78px"
                    />
                  </div>
                  <n-spin :show="historyLoading" class="phone-history-chart-spin">
                    <n-empty
                        v-if="!historyLoading && !hasChartData"
                        description="暂无历史预测样本"
                        style="padding: 16px 0;"
                    />
                    <div v-else-if="history" class="phone-history-chart-fill">
                      <AccuracyHistoryChart
                          :series="chartSeries"
                          :selected-day="selectedDay"
                          :window-days="chartWindowDays"
                          @select-day="selectChartDay"
                      />
                    </div>
                  </n-spin>
                </div>
              </div>
            </n-scrollbar>
          </div>
        </n-tab-pane>
      </n-tabs>

      <n-modal
          v-model:show="showDayStatsModal"
          preset="card"
          title="当日统计"
          to="body"
          :auto-focus="false"
          :bordered="false"
          :style="{
          width: 'min(420px, calc(100vw - 24px))',
          maxHeight: 'calc(100vh - 32px)',
          margin: 'auto',
        }"
      >
        <template #header-extra>
          <n-text depth="3" style="font-size: 12px;">{{ dayAccuracyHeaderExtra }}</n-text>
        </template>
        <n-spin :show="contentLoading">
          <AccuracyMetricsGrid
            :metrics="displayAccuracy"
            filterable
            :active-hit-key="filterHitKey"
            @filter-hit="onFilterHit"
          />
        </n-spin>
      </n-modal>
    </div>

    <!-- Phone / desktop: future schedule — same list chrome as calculator -->
    <div
        v-else-if="isScheduleFutureDay"
        ref="desktopListShellRef"
        class="fa-page-list-shell"
    >
      <n-alert
          v-if="error"
          type="error"
          title="获取失败"
          class="schedule-alert"
      >
        <n-space align="center" :size="12">
          <span>{{ error }}</span>
          <n-button size="small" type="primary" @click="loadScheduleDay()">重试</n-button>
        </n-space>
      </n-alert>
      <n-spin v-else :show="contentLoading" class="schedule-spin">
        <FixtureList
            :fixtures="scheduleDisplayedFixtures"
            :empty-description="scheduleEmptyText"
            :group-by-day="false"
            from="results"
            :date="selectedDay"
            :padding-top="12"
            :padding-bottom="20"
            markable
        />
      </n-spin>
      <ListBackTop
          :shell="desktopListShellRef"
          :content-key="scheduleDisplayedFixtures.length"
      />
    </div>

    <!-- Desktop: results day — list on the left, stats/chart on the right -->
    <template v-else>
      <n-layout-sider
          placement="left"
          class="results-list-sider"
          :width="345"
          :native-scrollbar="true"
          content-style="height: 100%; overflow: hidden; display: flex; flex-direction: column; background: var(--fa-bg-elevated); box-sizing: border-box;"
      >
        <div class="results-sider-head">
          <ResultsListToolbar
              v-model:team-search="teamSearch"
              :filter-options="shellFilterOptions"
              :tracked-ids="shellTrackedIds"
              :filter-active="shellFilterActive"
              :list-count="listedFixtures.length"
              :finished-count="listedFinishedCount"
              @confirm-filter="confirmFilter"
          />
        </div>
        <n-alert
            v-if="error"
            type="error"
            title="获取失败"
            class="results-sider-alert"
            style="flex-shrink: 0;"
        >
          <n-space align="center" :size="12">
            <span>{{ error }}</span>
            <n-button size="small" type="primary" @click="loadDayResults()">重试</n-button>
          </n-space>
        </n-alert>
        <div ref="desktopListShellRef" class="list-shell">
          <ResultsFixtureVirtualList
              :empty="!loading && !listedFixtures.length"
              :empty-description="emptyText"
              :items="listedVirtualRows"
              :content-loading="contentLoading"
              :filter-hit-key="filterHitKey"
              :padding-top="4"
              :padding-bottom="12"
              :items-style="resultsListItemsStyle"
              :marked-fixture-id="markedFixtureId"
              @open-detail="goDetail"
              @filter-hit="onFilterHit"
              @toggle-select="toggleMarked"
          />
          <ListBackTop
              :shell="desktopListShellRef"
              :content-key="listedFixtures.length"
              :bottom="16"
          />
        </div>
      </n-layout-sider>

      <n-layout
          class="results-main fa-page-main"
          content-style="display: flex; flex-direction: column; height: 100%; min-height: 0; background: var(--fa-bg); box-sizing: border-box;"
      >
        <div class="desktop-results-date-toolbar fa-page-toolbar">
          <HomeDateStrip v-model="selectedDay" />
        </div>

        <div class="results-dashboard">
          <n-grid :cols="20" :x-gap="10" :y-gap="10" style="flex-shrink: 0;">
          <n-gi :span="9">
            <n-card
                size="small"
                :bordered="false"
                class="accuracy-stat-card"
                :segmented="{ content: true }"
                style="background: var(--fa-bg-elevated); height: 100%;"
            >
              <template #header>
                <span class="accuracy-card-title">当日统计</span>
              </template>
              <template #header-extra>
                <n-text depth="3" style="font-size: 12px;user-select: none">{{ dayAccuracyHeaderExtra }}</n-text>
              </template>
              <n-spin :show="contentLoading">
                <AccuracyMetricsGrid
                  :metrics="displayAccuracy"
                  filterable
                  :active-hit-key="filterHitKey"
                  @filter-hit="onFilterHit"
                />
              </n-spin>
            </n-card>
          </n-gi>
          <n-gi :span="11">
            <n-card
                size="small"
                :bordered="false"
                class="accuracy-stat-card"
                :segmented="{ content: true }"
                style="background: var(--fa-bg-elevated); height: 100%;"
            >
              <template #header>
                <span class="accuracy-card-title">历史统计</span>
              </template>
              <template #header-extra>
                <n-text depth="3" style="font-size: 12px;user-select: none">{{ historyHeaderExtra }}</n-text>
              </template>
              <n-spin :show="historyLoading">
                <AccuracyMetricsGrid :metrics="history?.overall" />
              </n-spin>
            </n-card>
          </n-gi>
          </n-grid>

          <n-card
            size="small"
            :bordered="false"
            class="chart-card"
            :segmented="{ content: true }"
            style="background: var(--fa-bg-elevated);"
            content-style="flex: 1; min-height: 0; height: 100%; padding: 8px 12px 12px; display: flex; flex-direction: column;"
        >
          <template #header>
            <span class="accuracy-card-title">准确率走势</span>
          </template>
          <template #header-extra>
            <ChartWindowControls v-model="chartWindowDays" />
          </template>
          <n-spin
              :show="historyLoading"
              class="chart-spin"
              style="flex: 1; min-height: 0; height: 100%;"
          >
            <n-empty
                v-if="!historyLoading && !hasChartData"
                description="暂无历史预测样本"
                style="padding: 16px 0;"
            />
            <div v-else-if="history" class="chart-fill">
              <AccuracyHistoryChart
                  :series="chartSeries"
                  :selected-day="selectedDay"
                  :window-days="chartWindowDays"
                  @select-day="selectChartDay"
              />
            </div>
          </n-spin>
          </n-card>
        </div>
      </n-layout>
    </template>
  </n-layout>
</template>

<style scoped>
.results-layout {
  flex: 1;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.results-main :deep(> .n-layout-scroll-container) {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.results-list-sider {
  position: relative;
  z-index: 3;
  box-shadow: var(--fa-sider-shadow);
}

.desktop-results-date-toolbar {
  flex-shrink: 0;
  box-shadow: var(--fa-header-shadow);
}

.results-dashboard {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: var(--fa-content-block-start) var(--fa-content-inline)
    var(--fa-content-block-end);
  box-sizing: border-box;
  overflow: hidden;
}

.phone-results-tabs-wrap {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--fa-bg);
  padding: 0 var(--fa-content-inline) 4px;
  box-sizing: border-box;
}

.phone-results-tabs {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: transparent;
  border: 0;
  border-radius: 0;
  padding: 0;
  box-sizing: border-box;
}

.phone-results-tabs :deep(.n-tabs-nav) {
  flex-shrink: 0;
}

.phone-results-tabs :deep(.n-tabs-nav-scroll-content) {
  padding-top: 8px;
}

.phone-results-tabs :deep(.n-tabs-tab) {
  padding: 10px 10px 7px;
  font-size: 13px;
}

.phone-results-tabs :deep(.n-tabs-content),
.phone-results-tabs :deep(.n-tab-pane),
.phone-results-tabs :deep(.n-tabs-pane-wrapper),
.phone-results-tabs :deep(.n-tabs-pane-wrapper > div) {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.phone-tab-pane {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-top: 8px;
}

.phone-stat-pane {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 100%;
  box-sizing: border-box;
  padding: 0 0 12px;
}

.phone-tab-pane :deep(.n-scrollbar-content) {
  height: 100%;
  min-height: 100%;
}

.phone-history-chart-block {
  display: flex;
  flex: 1;
  min-height: 300px;
  flex-direction: column;
}

.phone-chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
  min-width: 0;
}

.chart-title-line {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: var(--fa-text-faint);
}

.phone-history-chart-spin {
  display: flex;
  flex: 1;
  flex-direction: column;
  height: 100%;
  min-height: 260px;
}

.phone-history-chart-spin :deep(.n-spin-content) {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.phone-history-chart-fill {
  flex: 1;
  width: 100%;
  min-height: 240px;
}

.phone-list-toolbar {
  flex-shrink: 0;
  padding: 0 0 8px;
}

.phone-list-alert {
  flex-shrink: 0;
  margin: 0 0 8px;
}

.schedule-alert {
  flex-shrink: 0;
  margin: 12px var(--fa-content-inline) 0;
}

.schedule-spin {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.schedule-spin :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.phone-list-pane {
  min-height: 0;
}

.results-sider-head {
  flex-shrink: 0;
  padding: 10px 12px 6px;
  box-sizing: border-box;
}

.results-sider-alert {
  margin: 0 12px 8px;
}

.list-shell {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-shell.phone {
  height: 100%;
}

.list-shell > :deep(.n-scrollbar),
.list-shell > :deep(.n-virtual-list),
.list-shell > :deep(.virtual-card-list) {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.chart-card {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.accuracy-card-title {
  font-weight: 600;
  user-select: none;
}

.chart-card :deep(.n-card-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chart-spin :deep(.n-spin-content),
.chart-spin :deep(.n-spin-container) {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chart-fill {
  flex: 1;
  min-height: 0;
  width: 100%;
  height: 100%;
}
</style>
