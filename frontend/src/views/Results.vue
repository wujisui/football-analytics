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
import ResultHitTags from '@/components/ResultHitTags.vue'
import FavoriteButton from '@/components/FavoriteButton.vue'
import ScoreDetailLink from '@/components/ScoreDetailLink.vue'
import ResultsFilterTrigger from '@/components/ResultsFilterTrigger.vue'
import { useFixturesShell } from '@/composables/useFixturesShell'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useFavoriteFixtures } from '@/composables/useFavoriteFixtures'
import { markDayAutoSynced, isDayAutoSynced, shouldAutoSyncDay } from '@/composables/useDayAutoSync'
import { publishResultsFixtures, publishScheduleFixtures, setResultsLoading, useResultsLeagues } from '@/composables/useResultsLeagues'
import { todayDate, yesterdayDate } from '@/utils/homeDateStrip'
import {
  formatDateTime,
  leagueTagColor,
  statusLabel,
  statusTagType,
} from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'
import {
  resultExtraScoreLine,
  resultScoreText,
} from '@/utils/resultsDisplay'
import { filterByTeamQuery, teamSearchEmptyHint } from '@/utils/teamSearch'
import {
  readResultsPageState,
  writeResultsPageState,
  type ResultsHitKey,
} from '@/utils/resultsPageState'

defineOptions({ name: 'Results' })

const ALL_HIT_KEYS: ResultsHitKey[] = ['score', 'result', 'ou', 'btts']
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

const filterHitKeys = ref<ResultsHitKey[]>([...ALL_HIT_KEYS])
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

const filteredFixtures = computed(() => {
  let list = fixtures.value.filter((fx) => trackedIdSet.value.has(fx.league_id))
  if (selectedLeagueId.value != null) {
    list = list.filter((fx) => fx.league_id === selectedLeagueId.value)
  }
  if (filterHitKeys.value.length && filterHitKeys.value.length < ALL_HIT_KEYS.length) {
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

const filterActive = computed(() => filterHitKeys.value.length !== ALL_HIT_KEYS.length)

function confirmHitFilter(hitKeys: ResultsHitKey[]) {
  if (!hitKeys.length) {
    message.warning('请至少勾选一个预测维度')
    return
  }
  filterHitKeys.value = hitKeys
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
  if (!filterActive.value) return dayAccuracy.value
  return summarizeFiltered(filteredFixtures.value)
})

const emptyText = computed(() => {
  if (!selectedDay.value) return '请选择日期'
  const teamHint = teamSearchEmptyHint(teamSearch.value)
  if (teamHint && filteredFixtures.value.length) return teamHint
  if (fixtures.value.length && !listedFixtures.value.length) {
    return '当前筛选下无场次，可调整预测维度'
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

const listTitle = computed(() => {
  if (isScheduleFutureDay.value) {
    const n = scheduleDisplayedFixtures.value.length
    const total = scheduleFixtures.value.filter((f) => trackedIdSet.value.has(f.league_id)).length
    if (total && n !== total) return `赛程 · ${selectedDay.value}（${n}/${total}）`
    return `赛程 · ${selectedDay.value}`
  }
  const n = listedFixtures.value.length
  const total = filteredFixtures.value.length
  if (total && n !== total) return `赛果 · ${selectedDay.value}（${n}/${total}）`
  return `赛果 · ${selectedDay.value}`
})

function formatRate(stat: AccuracyStat | undefined): string {
  if (!stat || stat.total <= 0 || stat.rate == null) return '—'
  return `${(stat.rate * 100).toFixed(0)}%（${stat.hits}/${stat.total}）`
}

function resultStatusTagType(
  status: string,
  statusShort?: string | null,
): ReturnType<typeof statusTagType> {
  if (status.toLowerCase() === 'finished') return 'error'
  return statusTagType(status, statusShort)
}

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
  filterHitKeys.value = [...ALL_HIT_KEYS]
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
      content-style="display: flex; flex-direction: column; height: 100%; padding: 12px; gap: 10px; background: var(--fa-bg); box-sizing: border-box; min-height: 0;"
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
          <div :style="isPhone ? 'padding: 8px 12px 20px;' : 'padding: 4px 14px 24px;'">
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
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%;">
            <span>{{ listTitle }}</span>
            <ResultsFilterTrigger
              :selected-hit-keys="filterHitKeys"
              :filter-active="filterActive"
              @confirm="confirmHitFilter"
            />
          </div>
        </template>
        <div ref="phoneListShellRef" class="results-list-shell phone">
          <n-scrollbar style="max-height: 100%; height: 100%;" trigger="hover">
            <div style="padding: 8px 12px 12px;">
              <n-spin :show="contentLoading">
                <n-empty
                  v-if="!loading && !listedFixtures.length"
                  :description="emptyText"
                  style="padding: 24px 12px;"
                />
                <n-list v-else>
                  <n-list-item v-for="fx in listedFixtures" :key="fx.fixture_id">
                    <n-thing>
                      <template #header>
                        <n-space :size="6" align="center" wrap style="width: 100%;">
                          <span>{{ fx.home_team_name }}</span>
                          <ScoreDetailLink
                            :label="resultScoreText(fx)"
                            @click="goDetail(fx.fixture_id)"
                          />
                          <span>{{ fx.away_team_name }}</span>
                          <FavoriteButton
                            :fixture-id="fx.fixture_id"
                            :result-fixture="fx"
                            size="tiny"
                          />
                        </n-space>
                        <n-text
                          v-if="resultExtraScoreLine(fx)"
                          depth="3"
                          style="display: block; font-size: 11px; font-weight: 400;"
                        >
                          {{ resultExtraScoreLine(fx) }}
                        </n-text>
                      </template>
                      <n-space
                        v-if="fx.has_prediction"
                        vertical
                        :size="4"
                        style="margin-top: 4px;"
                      >
                        <n-text depth="3" style="font-size: 11px;">
                          {{ fx.recommendation || '—' }}
                          · {{ fx.score_hint || '—' }}
                          · {{ fx.goal_lean || '—' }}
                          · {{ fx.both_score_lean || '—' }}
                        </n-text>
                        <ResultHitTags :fixture="fx" />
                      </n-space>
                      <n-text
                        v-else
                        depth="3"
                        style="display: block; margin-top: 4px; font-size: 11px;"
                      >
                        无赛前预测
                      </n-text>
                    </n-thing>
                  </n-list-item>
                </n-list>
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
      <div
        style="padding: 10px 12px 6px; flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; gap: 8px;"
      >
        <n-text strong>{{ listTitle }}</n-text>
        <ResultsFilterTrigger
          :selected-hit-keys="filterHitKeys"
          :filter-active="filterActive"
          @confirm="confirmHitFilter"
        />
      </div>
      <n-alert
        v-if="error"
        type="error"
        title="获取失败"
        style="margin: 0 12px 8px; flex-shrink: 0;"
      >
        <n-space align="center" :size="12">
          <span>{{ error }}</span>
          <n-button size="small" type="primary" @click="loadDayResults()">重试</n-button>
        </n-space>
      </n-alert>
      <div ref="desktopListShellRef" class="results-list-shell">
        <n-scrollbar style="height: 100%;" trigger="hover">
          <div style="padding: 4px 14px 16px;">
            <n-spin :show="contentLoading">
              <n-empty
                v-if="!loading && !listedFixtures.length"
                :description="emptyText"
                style="padding: 40px 12px;"
              />
              <n-list v-else style="background: transparent;">
                <n-list-item v-for="fx in listedFixtures" :key="fx.fixture_id">
                  <n-thing>
                    <template #header>
                      <n-space :size="6" align="center" wrap>
                        <n-tag
                          size="small"
                          :bordered="false"
                          :color="{
                            color: `${leagueTagColor(fx.league_id)}18`,
                            textColor: leagueTagColor(fx.league_id),
                          }"
                        >
                          {{ leagueLabel(fx.league_name) }}
                        </n-tag>
                        <span style="font-size: 12px; color: var(--fa-text-secondary);">
                          {{ formatDateTime(fx.fixture_date) }}
                        </span>
                      </n-space>
                    </template>
                    <template #header-extra>
                      <n-space :size="4" align="center">
                        <FavoriteButton
                          :fixture-id="fx.fixture_id"
                          :result-fixture="fx"
                          size="tiny"
                        />
                        <n-tag
                          size="small"
                          :type="resultStatusTagType(fx.status, fx.status_short)"
                          :bordered="false"
                        >
                          {{ statusLabel(fx.status, fx.status_short) }}
                        </n-tag>
                      </n-space>
                    </template>
                    <n-grid :cols="3" :x-gap="8" style="align-items: center; font-weight: 600;">
                      <n-gi style="text-align: right; font-size: 13px;">
                        {{ fx.home_team_name }}
                      </n-gi>
                      <n-gi style="text-align: center; font-variant-numeric: tabular-nums;">
                        <ScoreDetailLink
                          :label="resultScoreText(fx)"
                          @click="goDetail(fx.fixture_id)"
                        />
                        <div v-if="resultExtraScoreLine(fx)" class="score-extra">
                          {{ resultExtraScoreLine(fx) }}
                        </div>
                      </n-gi>
                      <n-gi style="font-size: 13px;">
                        {{ fx.away_team_name }}
                      </n-gi>
                    </n-grid>
                    <n-space
                      v-if="fx.has_prediction"
                      vertical
                      :size="4"
                      style="margin-top: 8px;"
                    >
                      <n-text depth="3" style="font-size: 11px;">
                        {{ fx.recommendation || '—' }}
                        · {{ fx.score_hint || '—' }}
                        · {{ fx.goal_lean || '—' }}
                        · {{ fx.both_score_lean || '—' }}
                      </n-text>
                      <ResultHitTags :fixture="fx" />
                    </n-space>
                    <n-text
                      v-else
                      depth="3"
                      style="display: block; margin-top: 6px; font-size: 11px;"
                    >
                      无赛前预测
                    </n-text>
                  </n-thing>
                </n-list-item>
              </n-list>
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

.score-extra {
  margin-top: 2px;
  font-size: 11px;
  font-weight: 500;
  color: var(--fa-text-secondary);
}
</style>
