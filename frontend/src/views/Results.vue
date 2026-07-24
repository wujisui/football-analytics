<script setup lang="ts">
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { ChevronDownOutline, ChevronUpOutline } from '@vicons/ionicons5'
import { useMessage } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'

import {
  fetchResults,
  fetchResultsHistory,
  fetchTodayFixtures,
  type ResultFixture,
  type ResultsAccuracy,
} from '@/api/fixtures'
import AccuracyHistoryChart from '@/components/AccuracyHistoryChart.vue'
import AccuracyStatistic from '@/components/AccuracyStatistic.vue'
import FixtureList from '@/components/FixtureList.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import ResultFixtureCard from '@/components/ResultFixtureCard.vue'
import ResultsListToolbar from '@/components/ResultsListToolbar.vue'
import { useFixturesShell } from '@/composables/useFixturesShell'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useFavoriteFixtures } from '@/composables/useFavoriteFixtures'
import {
  cacheResultsHistory,
  invalidateCachedResultsDay,
  publishResultsFixtures,
  publishScheduleFixtures,
  restoreCachedResultsDay,
  setResultsLoading,
  useResultsLeagues,
} from '@/composables/useResultsLeagues'
import { todayDate, yesterdayDate } from '@/utils/homeDateStrip'
import { ACCURACY_COLORS } from '@/utils/accuracyColors'
import { sortFixturesFavoritesFirst } from '@/utils/fixtureSort'
import { filterByTeamQuery, teamSearchEmptyHint } from '@/utils/teamSearch'
import {
  readResultsPageState,
  writeResultsPageState,
  RESULTS_ALL_HIT_KEYS,
  type ResultsHitKey,
} from '@/utils/resultsPageState'

defineOptions({ name: 'Results' })

const HIT_FIELD: Record<ResultsHitKey, keyof ResultFixture> = {
  result: 'result_hit',
  single_result: 'single_result_hit',
  score: 'score_hit',
  ou: 'ou_hit',
  btts: 'btts_hit',
  handicap: 'handicap_hit',
}

const isPhone = useIsPhone()
/** Phone: accuracy cards collapsed by default so the fixture list has room. */
const dayAccuracyExpanded = ref(false)
const historyAccuracyExpanded = ref(false)
const historyChartExpanded = ref(false)

function togglePhonePanel(panel: 'day' | 'history' | 'chart') {
  if (!isPhone.value) return
  const next =
    panel === 'day'
      ? !dayAccuracyExpanded.value
      : panel === 'history'
        ? !historyAccuracyExpanded.value
        : !historyChartExpanded.value
  dayAccuracyExpanded.value = panel === 'day' && next
  historyAccuracyExpanded.value = panel === 'history' && next
  historyChartExpanded.value = panel === 'chart' && next
}

const message = useMessage()
const route = useRoute()
const router = useRouter()
const { favoriteIds } = useFavoriteFixtures()

watch(isPhone, (phone) => {
  if (phone) {
    dayAccuracyExpanded.value = false
    historyAccuracyExpanded.value = false
    historyChartExpanded.value = false
  }
})
const {
  resultsTrackedIds,
  resultsFixtures,
  scheduleFixtures,
  resultsLoadedDay,
  resultsAccuracy,
  resultsHistory,
} = useResultsLeagues()
const {
  selectedDay,
  selectedLeagueId,
  teamSearch,
  contentLoading: shellContentLoading,
  isScheduleFutureDay,
  manualSyncRevision,
  manualSyncedDay,
  loadFilterOptions,
  syncFutureScheduleSelection,
} = useFixturesShell()

const desktopListShellRef = ref<HTMLElement | null>(null)
const phoneListShellRef = ref<HTMLElement | null>(null)

const fixtures = resultsFixtures
const dayAccuracy = resultsAccuracy
const history = resultsHistory
const loading = ref(false)
const historyLoading = ref(false)
const error = ref('')
const hint = ref('')

const filterHitKeys = ref<ResultsHitKey[]>([...RESULTS_ALL_HIT_KEYS])
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
  )
})

const leagueScopedFixtures = computed(() => {
  let list = fixtures.value.filter((fx) => trackedIdSet.value.has(fx.league_id))
  if (selectedLeagueId.value != null) {
    list = list.filter((fx) => fx.league_id === selectedLeagueId.value)
  }
  return list
})

const filteredFixtures = computed(() => {
  let list = leagueScopedFixtures.value
  if (filterHitKeys.value.length && filterHitKeys.value.length < RESULTS_ALL_HIT_KEYS.length) {
    const keys = filterHitKeys.value
    list = list.filter((fx) =>
      keys.some((k) => fx[HIT_FIELD[k]] === true),
    )
  }
  return list
})

const listedFixtures = computed(() =>
  sortFixturesFavoritesFirst(
    filterByTeamQuery(filteredFixtures.value, teamSearch.value),
    favoriteIds.value,
  ),
)

const filterActive = computed(
  () => filterHitKeys.value.length !== RESULTS_ALL_HIT_KEYS.length,
)

const activeHitFilterKey = computed(() => {
  if (filterHitKeys.value.length !== 1) return null
  return filterHitKeys.value[0]
})

function confirmHitFilter(hitKeys: ResultsHitKey[]) {
  if (!hitKeys.length) {
    message.warning('请至少勾选一个预测维度')
    return
  }
  filterHitKeys.value = hitKeys
}

/** Day panel hit count: exclusive filter for one dimension; click again to clear. */
function filterListByHitKey(key: ResultsHitKey) {
  if (activeHitFilterKey.value === key) {
    filterHitKeys.value = [...RESULTS_ALL_HIT_KEYS]
    return
  }
  filterHitKeys.value = [key]
}

/** Mirrors backend ``summarize_accuracy``; only counts rows with ``has_prediction``. */
function summarizeFiltered(list: ResultFixture[]): ResultsAccuracy {
  const rows = list.map((fx) => ({
    has_prediction: !!fx.has_prediction,
    evaluable: fx.home_goals != null && fx.away_goals != null,
    result_hit: fx.result_hit ?? null,
    single_result_hit: fx.single_result_hit ?? null,
    score_hit: fx.score_hit ?? null,
    ou_hit: fx.ou_hit ?? null,
    btts_hit: fx.btts_hit ?? null,
    handicap_hit: fx.handicap_hit ?? null,
  }))
  const rate = (
    key:
      | 'result_hit'
      | 'single_result_hit'
      | 'score_hit'
      | 'ou_hit'
      | 'btts_hit'
      | 'handicap_hit',
  ) => {
    const evalRows = rows.filter((r) => r.has_prediction && r[key] !== null && r[key] !== undefined)
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
    single_result: rate('single_result_hit'),
    score: rate('score_hit'),
    ou: rate('ou_hit'),
    btts: rate('btts_hit'),
    handicap: rate('handicap_hit'),
    fixtures_with_prediction: rows.filter((r) => r.has_prediction).length,
    fixtures_finished: rows.filter((r) => r.evaluable).length,
  }
}

/** Day panel always shows full-day (or league-scoped) stats, never hit-filtered. */
const displayAccuracy = computed(() => {
  if (selectedLeagueId.value == null) {
    return dayAccuracy.value
  }
  return summarizeFiltered(leagueScopedFixtures.value)
})

const emptyText = computed(() => {
  if (!selectedDay.value) return '请选择日期'
  const teamHint = teamSearchEmptyHint(teamSearch.value)
  if (teamHint && filteredFixtures.value.length) return teamHint
  if (fixtures.value.length && !listedFixtures.value.length) {
    return '当前筛选下无场次，可调整预测维度'
  }
  return `${selectedDay.value} 暂无已结束赛果，可点击「同步」手动更新`
})

const scheduleEmptyText = computed(() => {
  if (!selectedDay.value) return '请选择日期'
  const teamHint = teamSearchEmptyHint(teamSearch.value)
  if (teamHint && scheduleFixtures.value.length) return teamHint
  return `${selectedDay.value} 暂无未开赛赛程，可点击「同步」手动更新`
})

const historySampleCount = computed(
  () => history.value?.overall?.fixtures_with_prediction ?? 0,
)

const dayAccuracyHeaderExtra = computed(() => {
  const count = displayAccuracy.value?.fixtures_with_prediction ?? 0
  const day = selectedDay.value
  if (!day) return count ? `${count} 场` : '—'
  return `${count} 场 · ${day}`
})

/** History accordion: total predicted count + range start only. */
const historyRangeLabel = computed(() => {
  if (!history.value) return '全部入库'
  if (!historySampleCount.value) return '暂无已预测完场'
  const start = history.value.start_date
  return start
    ? `${historySampleCount.value} 场 · ${start}`
    : `${historySampleCount.value} 场`
})

const chartHeaderExtra = computed(() =>
  historySampleCount.value ? `${historySampleCount.value} 场` : '暂无样本',
)

const hasChartData = computed(
  () => (history.value?.series ?? []).some((p) => p.fixtures_with_prediction > 0),
)

function goDetail(fixtureId: number) {
  writeResultsPageState({
    date: selectedDay.value,
    filterHitKeys: filterHitKeys.value,
    teamSearch: teamSearch.value,
  })
  void router.push({
    name: 'fixture-detail',
    params: { fixtureId },
    query: { from: 'results', date: selectedDay.value },
  })
}

function applySavedFiltersIfAny() {
  const saved = readResultsPageState()
  if (!saved || saved.date !== selectedDay.value) return
  if (saved.filterHitKeys.length) {
    filterHitKeys.value = [...saved.filterHitKeys]
  }
  teamSearch.value = saved.teamSearch
}

async function loadDayResults() {
  if (!selectedDay.value) {
    fixtures.value = []
    dayAccuracy.value = null
    publishResultsFixtures([], selectedDay.value, null)
    return
  }
  loading.value = true
  setResultsLoading(true)
  error.value = ''
  try {
    const data = await fetchResults(selectedDay.value)
    publishResultsFixtures(
      data.fixtures,
      selectedDay.value,
      data.accuracy ?? null,
    )
    hint.value = data.total ? `共 ${data.total} 场` : ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取失败'
    publishResultsFixtures([], selectedDay.value, null)
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
    const cutoff = todayDate()
    cacheResultsHistory(
      await fetchResultsHistory({ days: 0, endDate: cutoff }),
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
  // Catalog is local-only; expose optional leagues before the user presses sync.
  void loadFilterOptions({ date: selectedDay.value }).catch(() => undefined)
  try {
    const data = await fetchTodayFixtures({ date: selectedDay.value, days: 1 })
    publishScheduleFixtures(data.fixtures, selectedDay.value)
    syncFutureScheduleSelection()
    hint.value = data.total ? `共 ${data.total} 场` : ''
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
    dayAccuracy.value = null
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

watch(selectedDay, () => {
  if (route.name !== 'results') return
  filterHitKeys.value = [...RESULTS_ALL_HIT_KEYS]
  void loadSelectedDay()
})

watch(manualSyncRevision, () => {
  if (
    route.name !== 'results'
    || manualSyncedDay.value !== selectedDay.value
  ) {
    return
  }
  void loadSelectedDay(true)
  void loadHistory(true)
})

onActivated(() => {
  if (isScheduleFutureDay.value) {
    if (resultsLoadedDay.value !== selectedDay.value) {
      void loadSelectedDay()
    }
    return
  }
  applySavedFiltersIfAny()
  if (resultsLoadedDay.value !== selectedDay.value) {
    void loadSelectedDay()
  }
})

onMounted(() => {
  const qDate = route.query.date
  let dayChanged = false
  if (typeof qDate === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(qDate)) {
    if (qDate !== selectedDay.value) {
      selectedDay.value = qDate
      dayChanged = true
    }
  } else if (selectedDay.value !== yesterdayDate()) {
    selectedDay.value = yesterdayDate()
    dayChanged = true
  }
  applySavedFiltersIfAny()
  if (!dayChanged && resultsLoadedDay.value !== selectedDay.value) {
    void loadSelectedDay()
  }
  void loadHistory()
})
</script>

<template>
  <n-layout
    class="results-layout"
    :has-sider="!isPhone"
    content-style="display: flex; flex-direction: column; height: 100%; min-height: 0;"
  >
    <n-layout
      class="results-main"
      content-style="display: flex; flex-direction: column; height: 100%; gap: 10px; background: var(--fa-bg); box-sizing: border-box; min-height: 0; padding: var(--fa-content-block-start) var(--fa-content-inline) var(--fa-content-block-end);"
    >
      <n-grid v-if="isResultsDay" :cols="isPhone ? 1 : 20" :x-gap="10" :y-gap="10" style="flex-shrink: 0;">
        <n-gi :span="isPhone ? 1 : 9">
          <n-card
            size="small"
            class="accuracy-stat-card"
            :class="{ collapsed: isPhone && !dayAccuracyExpanded }"
            :segmented="isPhone && !dayAccuracyExpanded ? false : { content: true }"
            style="background: var(--fa-bg-elevated); height: 100%;"
            :content-style="
              isPhone && !dayAccuracyExpanded ? 'display: none; padding: 0;' : undefined
            "
          >
            <template #header>
              <button
                type="button"
                class="accuracy-card-toggle"
                :class="{ phone: isPhone }"
                :disabled="!isPhone"
                :aria-expanded="!isPhone || dayAccuracyExpanded"
                @click="togglePhonePanel('day')"
              >
                <span>当日统计</span>
                <n-icon
                  v-if="isPhone"
                  :component="dayAccuracyExpanded ? ChevronUpOutline : ChevronDownOutline"
                  :size="16"
                />
              </button>
            </template>
            <template #header-extra>
              <n-text depth="3" style="font-size: 12px;">{{ dayAccuracyHeaderExtra }}</n-text>
            </template>
            <n-spin v-if="!isPhone || dayAccuracyExpanded" :show="contentLoading">
              <n-grid :cols="2" :x-gap="8" :y-gap="8" class="accuracy-metrics-grid">
                <n-gi>
                  <AccuracyStatistic
                    label="推荐结果"
                    :stat="displayAccuracy?.result"
                    :color="ACCURACY_COLORS.result"
                    hit-filterable
                    :hit-active="activeHitFilterKey === 'result'"
                    @filter-hits="filterListByHitKey('result')"
                  />
                </n-gi>
                <n-gi>
                  <AccuracyStatistic
                    label="胜平负单选"
                    :stat="displayAccuracy?.single_result"
                    :color="ACCURACY_COLORS.singleResult"
                    hit-filterable
                    :hit-active="activeHitFilterKey === 'single_result'"
                    @filter-hits="filterListByHitKey('single_result')"
                  />
                </n-gi>
                <n-gi>
                  <AccuracyStatistic
                    label="比分"
                    :stat="displayAccuracy?.score"
                    :color="ACCURACY_COLORS.score"
                    hit-filterable
                    :hit-active="activeHitFilterKey === 'score'"
                    @filter-hits="filterListByHitKey('score')"
                  />
                </n-gi>
                <n-gi>
                  <AccuracyStatistic
                    label="大小球"
                    :stat="displayAccuracy?.ou"
                    :color="ACCURACY_COLORS.ou"
                    hit-filterable
                    :hit-active="activeHitFilterKey === 'ou'"
                    @filter-hits="filterListByHitKey('ou')"
                  />
                </n-gi>
                <n-gi>
                  <AccuracyStatistic
                    label="双方进球"
                    :stat="displayAccuracy?.btts"
                    :color="ACCURACY_COLORS.btts"
                    hit-filterable
                    :hit-active="activeHitFilterKey === 'btts'"
                    @filter-hits="filterListByHitKey('btts')"
                  />
                </n-gi>
                <n-gi>
                  <AccuracyStatistic
                    label="让球胜平负"
                    :stat="displayAccuracy?.handicap"
                    :color="ACCURACY_COLORS.handicap"
                    hit-filterable
                    :hit-active="activeHitFilterKey === 'handicap'"
                    @filter-hits="filterListByHitKey('handicap')"
                  />
                </n-gi>
              </n-grid>
            </n-spin>
          </n-card>
        </n-gi>
        <n-gi :span="isPhone ? 1 : 11">
          <n-card
            size="small"
            class="accuracy-stat-card"
            :class="{ collapsed: isPhone && !historyAccuracyExpanded }"
            :segmented="isPhone && !historyAccuracyExpanded ? false : { content: true }"
            style="background: var(--fa-bg-elevated); height: 100%;"
            :content-style="
              isPhone && !historyAccuracyExpanded ? 'display: none; padding: 0;' : undefined
            "
          >
            <template #header>
              <button
                type="button"
                class="accuracy-card-toggle"
                :class="{ phone: isPhone }"
                :disabled="!isPhone"
                :aria-expanded="!isPhone || historyAccuracyExpanded"
                @click="togglePhonePanel('history')"
              >
                <span>历史统计</span>
                <n-icon
                  v-if="isPhone"
                  :component="historyAccuracyExpanded ? ChevronUpOutline : ChevronDownOutline"
                  :size="16"
                />
              </button>
            </template>
            <template #header-extra>
              <n-tooltip placement="bottom">
                <template #trigger>
                  <n-text depth="3" style="font-size: 12px;">
                    {{ historyRangeLabel }}
                  </n-text>
                </template>
                本地库全部已预测完场，起始 {{ history?.start_date || '—' }}，截止
                {{ todayDate() }}
              </n-tooltip>
            </template>
            <n-spin v-if="!isPhone || historyAccuracyExpanded" :show="historyLoading">
              <n-grid :cols="2" :x-gap="8" :y-gap="8" class="accuracy-metrics-grid">
                <n-gi>
                  <AccuracyStatistic
                    label="推荐结果"
                    :stat="history?.overall.result"
                    :color="ACCURACY_COLORS.result"
                  />
                </n-gi>
                <n-gi>
                  <AccuracyStatistic
                    label="胜平负单选"
                    :stat="history?.overall.single_result"
                    :color="ACCURACY_COLORS.singleResult"
                  />
                </n-gi>
                <n-gi>
                  <AccuracyStatistic
                    label="比分"
                    :stat="history?.overall.score"
                    :color="ACCURACY_COLORS.score"
                  />
                </n-gi>
                <n-gi>
                  <AccuracyStatistic
                    label="大小球"
                    :stat="history?.overall.ou"
                    :color="ACCURACY_COLORS.ou"
                  />
                </n-gi>
                <n-gi>
                  <AccuracyStatistic
                    label="双方进球"
                    :stat="history?.overall.btts"
                    :color="ACCURACY_COLORS.btts"
                  />
                </n-gi>
                <n-gi>
                  <AccuracyStatistic
                    label="让球胜平负"
                    :stat="history?.overall.handicap"
                    :color="ACCURACY_COLORS.handicap"
                  />
                </n-gi>
              </n-grid>
            </n-spin>
          </n-card>
        </n-gi>
      </n-grid>

      <n-card
        v-if="isResultsDay"
        size="small"
        class="chart-card"
        :class="{
          'phone-collapsed': isPhone && !historyChartExpanded,
          'phone-expanded': isPhone && historyChartExpanded,
        }"
        :segmented="isPhone && !historyChartExpanded ? false : { content: true }"
        style="background: var(--fa-bg-elevated);"
        :content-style="
          isPhone && !historyChartExpanded
            ? 'display: none; padding: 0;'
            : 'flex: 1; min-height: 0; height: 100%; padding: 8px 12px 12px; display: flex; flex-direction: column;'
        "
      >
        <template #header>
          <button
            type="button"
            class="accuracy-card-toggle"
            :class="{ phone: isPhone }"
            :disabled="!isPhone"
            :aria-expanded="!isPhone || historyChartExpanded"
            @click="togglePhonePanel('chart')"
          >
            <span>准确率走势</span>
            <n-icon
              v-if="isPhone"
              :component="historyChartExpanded ? ChevronUpOutline : ChevronDownOutline"
              :size="16"
            />
          </button>
        </template>
        <template #header-extra>
          <n-tooltip placement="bottom">
            <template #trigger>
              <n-text depth="3" style="font-size: 12px;">
                {{ chartHeaderExtra }}
              </n-text>
            </template>
            走势截止 {{ todayDate() }}，与顶部日期选择无关
          </n-tooltip>
        </template>
        <n-spin
          v-if="!isPhone || historyChartExpanded"
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
            <AccuracyHistoryChart :series="history.series" />
          </div>
        </n-spin>
      </n-card>

      <n-alert
        v-if="error && isScheduleFutureDay"
        type="error"
        title="获取失败"
        style="flex-shrink: 0;"
      >
        <n-space align="center" :size="12">
          <span>{{ error }}</span>
          <n-button size="small" type="primary" @click="loadScheduleDay()">重试</n-button>
        </n-space>
      </n-alert>

      <div
        v-if="isScheduleFutureDay"
        ref="desktopListShellRef"
        class="schedule-list-shell"
        :class="{ phone: isPhone }"
      >
        <n-scrollbar style="height: 100%;" trigger="hover">
          <div :class="isPhone ? 'schedule-list-inner phone' : 'schedule-list-inner'">
            <n-spin :show="contentLoading">
              <FixtureList
                :fixtures="scheduleDisplayedFixtures"
                :empty-description="scheduleEmptyText"
                :group-by-day="false"
                from="results"
                :date="selectedDay"
              />
            </n-spin>
          </div>
        </n-scrollbar>
        <ListBackTop :shell="desktopListShellRef" :bottom="16" />
      </div>

      <n-card
        v-if="isPhone && isResultsDay"
        size="small"
        :segmented="{ content: true }"
        class="phone-results-card"
        style="min-height: 0; display: flex; flex-direction: column; background: var(--fa-bg-elevated);"
        content-style="flex: 1; min-height: 0; padding: 0;"
      >
        <template #header>
          <ResultsListToolbar
            v-model:team-search="teamSearch"
            :selected-hit-keys="filterHitKeys"
            :filter-active="filterActive"
            @confirm-filter="confirmHitFilter"
          />
        </template>
        <div ref="phoneListShellRef" class="results-list-shell phone">
          <n-scrollbar style="max-height: 100%; height: 100%;" trigger="hover">
            <div class="results-list-inner">
              <n-spin :show="contentLoading">
                <n-empty
                  v-if="!loading && !listedFixtures.length"
                  :description="emptyText"
                  style="padding: 24px 12px;"
                />
                <div v-else class="results-card-stack">
                  <ResultFixtureCard
                    v-for="fx in listedFixtures"
                    :key="fx.fixture_id"
                    :fixture="fx"
                    @open-detail="goDetail"
                  />
                </div>
              </n-spin>
            </div>
          </n-scrollbar>
          <ListBackTop :shell="phoneListShellRef" :right="12" :bottom="12" />
        </div>
      </n-card>
    </n-layout>

    <n-layout-sider
      v-if="!isPhone && isResultsDay"
      placement="right"
      bordered
      :width="320"
      :native-scrollbar="true"
      content-style="height: 100%; overflow: hidden; display: flex; flex-direction: column; background: var(--fa-bg-elevated); box-sizing: border-box;"
    >
      <div class="results-sider-head">
        <ResultsListToolbar
          v-model:team-search="teamSearch"
          :selected-hit-keys="filterHitKeys"
          :filter-active="filterActive"
          @confirm-filter="confirmHitFilter"
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
      <div ref="desktopListShellRef" class="results-list-shell">
        <n-scrollbar style="height: 100%;" trigger="hover">
          <div class="results-list-inner">
            <n-spin :show="contentLoading">
              <n-empty
                v-if="!loading && !listedFixtures.length"
                :description="emptyText"
                style="padding: 40px 12px;"
              />
              <div v-else class="results-card-stack">
                <ResultFixtureCard
                  v-for="fx in listedFixtures"
                  :key="fx.fixture_id"
                  :fixture="fx"
                  @open-detail="goDetail"
                />
              </div>
            </n-spin>
          </div>
        </n-scrollbar>
        <ListBackTop :shell="desktopListShellRef" :bottom="16" />
      </div>
    </n-layout-sider>
  </n-layout>
</template>

<style scoped>
.results-layout {
  flex: 1;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.schedule-list-inner {
  padding-top: 4px;
}

.schedule-list-inner.phone {
  padding: 8px 0 20px;
}

.results-sider-head {
  flex-shrink: 0;
  padding: 10px var(--fa-content-inline) 6px;
}

.results-list-inner {
  padding: 0 8px 8px;
  box-sizing: border-box;
}

.results-card-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.results-sider-alert {
  margin: 0 var(--fa-content-inline) 8px;
}

.schedule-list-shell {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.schedule-list-shell.phone {
  flex: 1;
  min-height: 0;
}

.results-list-shell {
  position: relative;
  flex: 1;
  min-height: 0;
}

.results-list-shell.phone {
  height: 100%;
}

.chart-card {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.chart-card.phone-collapsed {
  flex: 0 0 auto;
  min-height: auto;
}

.chart-card.phone-expanded {
  flex: 0 0 42%;
  min-height: 220px;
}

.accuracy-card-toggle {
  appearance: none;
  margin: 0;
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  text-align: left;
  cursor: default;
}

.accuracy-card-toggle.phone {
  cursor: pointer;
}

.accuracy-card-toggle:disabled {
  cursor: default;
}

.accuracy-stat-card.collapsed :deep(.n-card-header),
.chart-card.phone-collapsed :deep(.n-card-header) {
  padding-bottom: 10px;
}

.accuracy-metrics-grid :deep(.n-grid-item) {
  min-width: 0;
}

.phone-results-card {
  flex: 1 1 auto;
}

.chart-card :deep(.n-card__content) {
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
