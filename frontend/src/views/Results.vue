<script setup lang="ts">
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'

import { enqueueBackgroundSync } from '@/composables/useBackgroundSync'
import {
  fetchResults,
  fetchResultsHistory,
  fetchTodayFixtures,
  type AccuracyStat,
  type ResultFixture,
  type ResultsAccuracy,
  type ResultsHistoryResponse,
} from '@/api/fixtures'
import AccuracyHistoryChart from '@/components/AccuracyHistoryChart.vue'
import FixtureList from '@/components/FixtureList.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import ResultFixtureCard from '@/components/ResultFixtureCard.vue'
import ResultsListToolbar from '@/components/ResultsListToolbar.vue'
import { useFixturesShell } from '@/composables/useFixturesShell'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useFavoriteFixtures } from '@/composables/useFavoriteFixtures'
import { markDayAutoSynced, isDayAutoSynced, shouldAutoSyncDay } from '@/composables/useDayAutoSync'
import { publishResultsFixtures, publishScheduleFixtures, setResultsLoading, useResultsLeagues } from '@/composables/useResultsLeagues'
import { todayDate, yesterdayDate } from '@/utils/homeDateStrip'
import { filterByTeamQuery, teamSearchEmptyHint } from '@/utils/teamSearch'
import {
  readResultsPageState,
  writeResultsPageState,
  RESULTS_ALL_HIT_KEYS,
  type ResultsFilterConfirm,
  type ResultsHitKey,
} from '@/utils/resultsPageState'

defineOptions({ name: 'Results' })

const HIT_FIELD: Record<ResultsHitKey, keyof ResultFixture> = {
  result: 'result_hit',
  score: 'score_hit',
  ou: 'ou_hit',
  btts: 'btts_hit',
}

const isPhone = useIsPhone()
const message = useMessage()
const route = useRoute()
const router = useRouter()
const { favoriteIds, syncFavoriteFromResult } = useFavoriteFixtures()
const {
  resultsTrackedIds,
  scheduleFixtures,
} = useResultsLeagues()
const {
  selectedDay,
  selectedLeagueId,
  teamSearch,
  contentLoading: shellContentLoading,
  isScheduleFutureDay,
} = useFixturesShell()

const desktopListShellRef = ref<HTMLElement | null>(null)
const phoneListShellRef = ref<HTMLElement | null>(null)

const fixtures = ref<ResultFixture[]>([])
const dayAccuracy = ref<ResultsAccuracy | null>(null)
const history = ref<ResultsHistoryResponse | null>(null)
const loading = ref(false)
const historyLoading = ref(false)
const error = ref('')
const hint = ref('')

const filterHitKeys = ref<ResultsHitKey[]>([...RESULTS_ALL_HIT_KEYS])
const hideWithoutPrediction = ref(false)
const loadedResultsDay = ref('')

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
  return filterByTeamQuery(list, teamSearch.value)
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
  if (hideWithoutPrediction.value) {
    list = list.filter((fx) => fx.has_prediction)
  }
  if (filterHitKeys.value.length && filterHitKeys.value.length < RESULTS_ALL_HIT_KEYS.length) {
    const keys = filterHitKeys.value
    list = list.filter((fx) =>
      keys.some((k) => fx[HIT_FIELD[k]] === true),
    )
  }
  return list
})

const listedFixtures = computed(() => {
  const list = filterByTeamQuery(filteredFixtures.value, teamSearch.value)
  return [...list]
    .map((fx, index) => ({ fx, index }))
    .sort((a, b) => {
      const aFav = favoriteIds.value.has(a.fx.fixture_id)
      const bFav = favoriteIds.value.has(b.fx.fixture_id)
      if (aFav !== bFav) return aFav ? -1 : 1
      if (aFav && bFav) return a.fx.fixture_date.localeCompare(b.fx.fixture_date)
      return a.index - b.index
    })
    .map(({ fx }) => fx)
})

const filterActive = computed(
  () =>
    filterHitKeys.value.length !== RESULTS_ALL_HIT_KEYS.length
    || hideWithoutPrediction.value,
)

function confirmHitFilter(payload: ResultsFilterConfirm) {
  if (!payload.hitKeys.length) {
    message.warning('请至少勾选一个预测维度')
    return
  }
  filterHitKeys.value = payload.hitKeys
  hideWithoutPrediction.value = payload.hideWithoutPrediction
}

function summarizeFiltered(list: ResultFixture[]): ResultsAccuracy {
  const rows = list.map((fx) => ({
    has_prediction: !!fx.has_prediction,
    evaluable: fx.home_goals != null && fx.away_goals != null,
    result_hit: fx.result_hit ?? null,
    score_hit: fx.score_hit ?? null,
    ou_hit: fx.ou_hit ?? null,
    btts_hit: fx.btts_hit ?? null,
  }))
  const rate = (key: 'result_hit' | 'score_hit' | 'ou_hit' | 'btts_hit') => {
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
    score: rate('score_hit'),
    ou: rate('ou_hit'),
    btts: rate('btts_hit'),
    fixtures_with_prediction: rows.filter((r) => r.has_prediction).length,
    fixtures_finished: rows.filter((r) => r.evaluable).length,
  }
}

const displayAccuracy = computed(() => {
  if (!filterActive.value && selectedLeagueId.value == null) {
    return dayAccuracy.value
  }
  const base = filterActive.value ? filteredFixtures.value : leagueScopedFixtures.value
  return summarizeFiltered(base)
})

const emptyText = computed(() => {
  if (!selectedDay.value) return '请选择日期'
  const teamHint = teamSearchEmptyHint(teamSearch.value)
  if (teamHint && filteredFixtures.value.length) return teamHint
  if (fixtures.value.length && !listedFixtures.value.length) {
    return hideWithoutPrediction.value
      ? '当前筛选下无场次，可取消「隐藏无赛前预测」或调整预测维度'
      : '当前筛选下无场次，可调整预测维度'
  }
  if (
    isDayAutoSynced(selectedDay.value) &&
    !fixtures.value.length &&
    !contentLoading.value
  ) {
    return `${selectedDay.value} 当日没有比赛数据`
  }
  return `${selectedDay.value} 暂无已结束赛果`
})

const scheduleEmptyText = computed(() => {
  if (!selectedDay.value) return '请选择日期'
  const teamHint = teamSearchEmptyHint(teamSearch.value)
  if (teamHint && scheduleFixtures.value.length) return teamHint
  if (
    isDayAutoSynced(selectedDay.value) &&
    !scheduleFixtures.value.length &&
    !contentLoading.value
  ) {
    return `${selectedDay.value} 当日没有比赛数据`
  }
  return `${selectedDay.value} 暂无未开赛赛程`
})

const historySampleCount = computed(
  () => history.value?.overall?.fixtures_with_prediction ?? 0,
)

const historyRangeLabel = computed(() => {
  if (!history.value) return '全部入库'
  if (!historySampleCount.value) return '暂无已预测完场'
  const { start_date: start, end_date: end } = history.value
  if (start && end) {
    return start === end
      ? `已预测 ${historySampleCount.value} 场（${start}）`
      : `已预测 ${historySampleCount.value} 场（${start} ~ ${end}）`
  }
  return `已预测 ${historySampleCount.value} 场`
})

const hasChartData = computed(
  () => (history.value?.series ?? []).some((p) => p.fixtures_with_prediction > 0),
)

function formatRate(stat: AccuracyStat | undefined): string {
  if (!stat || stat.total <= 0 || stat.rate == null) return '—'
  return `${(stat.rate * 100).toFixed(0)}%（${stat.hits}/${stat.total}）`
}

function goDetail(fixtureId: number) {
  writeResultsPageState({
    date: selectedDay.value,
    filterHitKeys: filterHitKeys.value,
    hideWithoutPrediction: hideWithoutPrediction.value,
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
  hideWithoutPrediction.value = saved.hideWithoutPrediction === true
  teamSearch.value = saved.teamSearch
}

async function loadDayResults() {
  if (!selectedDay.value) {
    fixtures.value = []
    dayAccuracy.value = null
    publishResultsFixtures([], selectedDay.value)
    loadedResultsDay.value = ''
    return
  }
  loading.value = true
  setResultsLoading(true)
  error.value = ''
  try {
    const data = await fetchResults(selectedDay.value)
    fixtures.value = data.fixtures
    publishResultsFixtures(data.fixtures, selectedDay.value)
    dayAccuracy.value = data.accuracy ?? null
    hint.value = data.total ? `共 ${data.total} 场` : ''
    for (const fx of fixtures.value) {
      if (favoriteIds.value.has(fx.fixture_id)) {
        syncFavoriteFromResult(fx)
      }
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取失败'
    fixtures.value = []
    dayAccuracy.value = null
    publishResultsFixtures([], selectedDay.value)
  } finally {
    loading.value = false
    setResultsLoading(false)
    loadedResultsDay.value = selectedDay.value
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const cutoff = todayDate()
    history.value = await fetchResultsHistory({ days: 0, endDate: cutoff })
  } catch {
    history.value = null
  } finally {
    historyLoading.value = false
  }
}

async function loadScheduleDay() {
  if (!selectedDay.value) {
    publishScheduleFixtures([], selectedDay.value)
    loadedResultsDay.value = ''
    return
  }
  loading.value = true
  setResultsLoading(true)
  error.value = ''
  try {
    const data = await fetchTodayFixtures({ date: selectedDay.value, days: 1 })
    publishScheduleFixtures(data.fixtures, selectedDay.value)
    hint.value = data.total ? `共 ${data.total} 场` : ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取失败'
    publishScheduleFixtures([], selectedDay.value)
  } finally {
    loading.value = false
    setResultsLoading(false)
    loadedResultsDay.value = selectedDay.value
  }
}

async function syncAndLoadDay() {
  if (!selectedDay.value) {
    fixtures.value = []
    dayAccuracy.value = null
    publishResultsFixtures([], selectedDay.value)
    publishScheduleFixtures([], selectedDay.value)
    return
  }

  if (isScheduleFutureDay.value) {
    await loadScheduleDay()
    const day = selectedDay.value
    if (!shouldAutoSyncDay(day, scheduleFixtures.value.length > 0)) return
    enqueueBackgroundSync(
      {
        date: day,
        days: 1,
        includeResults: false,
        includeOdds: true,
      },
      (_ok) => {
        markDayAutoSynced(day)
        void loadScheduleDay()
      },
    )
    return
  }

  await loadDayResults()

  const day = selectedDay.value
  if (!shouldAutoSyncDay(day, fixtures.value.length > 0)) return

  enqueueBackgroundSync(
    {
      date: day,
      days: 1,
      includeResults: true,
      includeOdds: false,
    },
    (_ok) => {
      markDayAutoSynced(day)
      void loadDayResults()
    },
  )
}

watch(selectedDay, () => {
  if (route.name !== 'results') return
  filterHitKeys.value = [...RESULTS_ALL_HIT_KEYS]
  hideWithoutPrediction.value = false
  void syncAndLoadDay()
})

onActivated(() => {
  if (isScheduleFutureDay.value) {
    if (loadedResultsDay.value !== selectedDay.value) {
      void syncAndLoadDay()
    } else {
      publishScheduleFixtures(scheduleFixtures.value, selectedDay.value)
    }
    return
  }
  applySavedFiltersIfAny()
  if (loadedResultsDay.value !== selectedDay.value) {
    void syncAndLoadDay()
  } else {
    publishResultsFixtures(fixtures.value, selectedDay.value)
  }
})

onMounted(() => {
  const qDate = route.query.date
  if (typeof qDate === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(qDate)) {
    if (qDate !== selectedDay.value) {
      selectedDay.value = qDate
    }
  } else {
    selectedDay.value = yesterdayDate()
  }
  applySavedFiltersIfAny()
  void syncAndLoadDay()
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
      <n-grid v-if="isResultsDay" :cols="isPhone ? 1 : 2" :x-gap="10" :y-gap="10" style="flex-shrink: 0;">
        <n-gi>
          <n-card
            size="small"
            title="当日预测准确率"
            :segmented="{ content: true }"
            style="background: var(--fa-bg-elevated); height: 100%;"
          >
            <template #header-extra>
              <n-text depth="3" style="font-size: 12px;">{{ selectedDay }}</n-text>
            </template>
            <n-spin :show="contentLoading">
              <n-grid :cols="2" :x-gap="8" :y-gap="8">
                <n-gi>
                  <n-statistic label="胜平负" :value="formatRate(displayAccuracy?.result)" />
                </n-gi>
                <n-gi>
                  <n-statistic label="比分" :value="formatRate(displayAccuracy?.score)" />
                </n-gi>
                <n-gi>
                  <n-statistic label="大小球" :value="formatRate(displayAccuracy?.ou)" />
                </n-gi>
                <n-gi>
                  <n-statistic label="双方进球" :value="formatRate(displayAccuracy?.btts)" />
                </n-gi>
              </n-grid>
            </n-spin>
          </n-card>
        </n-gi>
        <n-gi>
          <n-card
            size="small"
            title="历史总预测准确率"
            :segmented="{ content: true }"
            style="background: var(--fa-bg-elevated); height: 100%;"
          >
            <template #header-extra>
              <n-tooltip placement="bottom">
                <template #trigger>
                  <n-text depth="3" style="font-size: 12px;">
                    {{ historyRangeLabel }}
                  </n-text>
                </template>
                本地库全部已预测完场，截止 {{ todayDate() }}
              </n-tooltip>
            </template>
            <n-spin :show="historyLoading">
              <n-grid :cols="2" :x-gap="8" :y-gap="8">
                <n-gi>
                  <n-statistic label="胜平负" :value="formatRate(history?.overall.result)" />
                </n-gi>
                <n-gi>
                  <n-statistic label="比分" :value="formatRate(history?.overall.score)" />
                </n-gi>
                <n-gi>
                  <n-statistic label="大小球" :value="formatRate(history?.overall.ou)" />
                </n-gi>
                <n-gi>
                  <n-statistic label="双方进球" :value="formatRate(history?.overall.btts)" />
                </n-gi>
              </n-grid>
            </n-spin>
          </n-card>
        </n-gi>
      </n-grid>

      <n-card
        v-if="isResultsDay"
        size="small"
        title="准确率走势"
        :segmented="{ content: true }"
        class="chart-card"
        style="flex: 1; min-height: 0; background: var(--fa-bg-elevated);"
        content-style="flex: 1; min-height: 0; height: 100%; padding: 8px 12px 12px; display: flex; flex-direction: column;"
      >
        <template #header-extra>
          <n-tooltip placement="bottom">
            <template #trigger>
              <n-text depth="3" style="font-size: 12px;">
                {{
                  historySampleCount
                    ? `有预测样本 ${historySampleCount} 场`
                    : '仅含有预测样本的日期'
                }}
              </n-text>
            </template>
            走势截止 {{ todayDate() }}，与顶部日期选择无关
          </n-tooltip>
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
        style="flex: 0 0 42%; min-height: 0; display: flex; flex-direction: column; background: var(--fa-bg-elevated);"
        content-style="flex: 1; min-height: 0; padding: 0;"
      >
        <template #header>
          <ResultsListToolbar
            v-model:team-search="teamSearch"
            :selected-hit-keys="filterHitKeys"
            :hide-without-prediction="hideWithoutPrediction"
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
          :hide-without-prediction="hideWithoutPrediction"
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
