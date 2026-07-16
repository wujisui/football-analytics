<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'

import {
  fetchResults,
  fetchResultsHistory,
  syncFixtures,
  type AccuracyStat,
  type ResultFixture,
  type ResultsAccuracy,
  type ResultsHistoryResponse,
} from '@/api/fixtures'
import AccuracyHistoryChart from '@/components/AccuracyHistoryChart.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import PageToolbarActions from '@/components/PageToolbarActions.vue'
import PageToolbarSearch from '@/components/PageToolbarSearch.vue'
import ResultHitTags from '@/components/ResultHitTags.vue'
import ScoreDetailLink from '@/components/ScoreDetailLink.vue'
import ResultsFilterTrigger, {
  type ResultsHitKey,
} from '@/components/ResultsFilterTrigger.vue'
import { useIsPhone } from '@/composables/useMediaQuery'
import { markDayAutoSynced, isDayAutoSynced, shouldAutoSyncDay } from '@/composables/useDayAutoSync'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import {
  formatDateTime,
  leagueTagColor,
  statusLabel,
  statusTagType,
} from '@/utils/format'
import { leagueNameZh } from '@/utils/leagueNames'
import {
  resultExtraScoreLine,
  resultScoreText,
} from '@/utils/resultsDisplay'
import { filterByTeamQuery, teamSearchEmptyHint } from '@/utils/teamSearch'

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

const desktopListShellRef = ref<HTMLElement | null>(null)
const phoneListShellRef = ref<HTMLElement | null>(null)

const { todayDate } = useHomeFixtures()

const selectedDate = ref(todayDate())
const fixtures = ref<ResultFixture[]>([])
const dayAccuracy = ref<ResultsAccuracy | null>(null)
const history = ref<ResultsHistoryResponse | null>(null)
const loading = ref(false)
const historyLoading = ref(false)
const syncing = ref(false)
const error = ref('')
const hint = ref('')

/** Applied filters — default all leagues of the day + all hit dimensions. */
const filterLeagueIds = ref<number[]>([])
const filterHitKeys = ref<ResultsHitKey[]>([...ALL_HIT_KEYS])
const teamSearch = ref('')

const contentLoading = computed(() => loading.value || syncing.value)

const leagueOptions = computed(() => {
  const map = new Map<number, string>()
  for (const fx of fixtures.value) {
    if (!map.has(fx.league_id)) {
      map.set(fx.league_id, leagueNameZh(fx.league_name))
    }
  }
  return [...map.entries()]
    .sort((a, b) => a[1].localeCompare(b[1], 'zh'))
    .map(([league_id, label]) => ({ league_id, label }))
})

const allDayLeagueIds = computed(() => leagueOptions.value.map((o) => o.league_id))

function syncFilterLeaguesToDay() {
  const allow = new Set(allDayLeagueIds.value)
  const kept = filterLeagueIds.value.filter((id) => allow.has(id))
  filterLeagueIds.value = kept.length ? kept : [...allDayLeagueIds.value]
}

const filterActive = computed(() => {
  const leagues = allDayLeagueIds.value
  if (!leagues.length) return false
  if (filterLeagueIds.value.length !== leagues.length) return true
  if (filterHitKeys.value.length !== ALL_HIT_KEYS.length) return true
  const set = new Set(filterLeagueIds.value)
  return leagues.some((id) => !set.has(id))
})

function confirmFilter(payload: { leagueIds: number[]; hitKeys: ResultsHitKey[] }) {
  if (!payload.leagueIds.length) {
    message.warning('请至少勾选一个联赛')
    return
  }
  if (!payload.hitKeys.length) {
    message.warning('请至少勾选一个预测维度')
    return
  }
  filterLeagueIds.value = payload.leagueIds
  filterHitKeys.value = payload.hitKeys
}

const filteredFixtures = computed(() => {
  const leagueSet = new Set(filterLeagueIds.value)
  let list = fixtures.value.filter((fx) => leagueSet.has(fx.league_id))
  // All hit dims checked → no hit filter; otherwise keep fixtures that hit any checked dim.
  if (filterHitKeys.value.length && filterHitKeys.value.length < ALL_HIT_KEYS.length) {
    const keys = filterHitKeys.value
    list = list.filter((fx) =>
      keys.some((k) => fx[HIT_FIELD[k]] === true),
    )
  }
  return list
})

const listedFixtures = computed(() =>
  filterByTeamQuery(filteredFixtures.value, teamSearch.value),
)

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
  if (!selectedDate.value) return '请选择日期'
  const teamHint = teamSearchEmptyHint(teamSearch.value)
  if (teamHint && filteredFixtures.value.length) return teamHint
  if (fixtures.value.length && !listedFixtures.value.length) {
    return '当前筛选下无场次，可调整联赛 / 预测维度'
  }
  if (
    isDayAutoSynced(selectedDate.value) &&
    !fixtures.value.length &&
    !contentLoading.value
  ) {
    return `${selectedDate.value} 当日没有比赛数据`
  }
  return `${selectedDate.value} 暂无已结束赛果`
})

const subtitle = computed(() => hint.value || undefined)

/** Sample count only — not tied to the day picker. */
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
  const n = listedFixtures.value.length
  const total = filteredFixtures.value.length
  if (total && n !== total) return `赛果列表 · ${selectedDate.value}（${n}/${total}）`
  return `赛果列表 · ${selectedDate.value}`
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
  void router.push({
    name: 'fixture-detail',
    params: { fixtureId },
    query: { from: 'results', date: selectedDate.value },
  })
}

async function loadDayResults() {
  if (!selectedDate.value) {
    fixtures.value = []
    dayAccuracy.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await fetchResults(selectedDate.value)
    fixtures.value = data.fixtures
    dayAccuracy.value = data.accuracy ?? null
    hint.value = data.total ? `共 ${data.total} 场` : ''
    syncFilterLeaguesToDay()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取失败'
    fixtures.value = []
    dayAccuracy.value = null
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    // All local finished samples — independent of day picker / day filters.
    history.value = await fetchResultsHistory({ days: 0 })
  } catch {
    history.value = null
  } finally {
    historyLoading.value = false
  }
}

async function syncAndLoadDay() {
  if (!selectedDate.value) {
    fixtures.value = []
    dayAccuracy.value = null
    return
  }

  await loadDayResults()

  const day = selectedDate.value
  if (!shouldAutoSyncDay(day, fixtures.value.length > 0)) return

  syncing.value = true
  error.value = ''
  hint.value = ''
  try {
    await syncFixtures({
      date: day,
      days: 1,
      includeResults: true,
    })
    markDayAutoSynced(day)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取失败'
    markDayAutoSynced(day)
  } finally {
    syncing.value = false
  }

  await loadDayResults()
}

watch(selectedDate, () => {
  filterLeagueIds.value = []
  filterHitKeys.value = [...ALL_HIT_KEYS]
  void syncAndLoadDay()
})

onMounted(() => {
  const qDate = route.query.date
  if (
    typeof qDate === 'string' &&
    /^\d{4}-\d{2}-\d{2}$/.test(qDate) &&
    qDate !== selectedDate.value
  ) {
    selectedDate.value = qDate
  } else {
    void syncAndLoadDay()
  }
  void loadHistory()
})
</script>

<template>
  <div class="fa-page-frame">
  <n-layout
    class="results-layout fa-page-shell"
    content-style="display: flex; flex-direction: column; height: 100%; background: var(--fa-bg);"
  >
    <n-layout-header bordered class="fa-page-toolbar" style="flex-shrink: 0;">
      <div class="fa-toolbar-top">
        <n-breadcrumb class="fa-toolbar-crumb">
          <n-breadcrumb-item>赛果</n-breadcrumb-item>
          <n-breadcrumb-item>{{ selectedDate }}</n-breadcrumb-item>
        </n-breadcrumb>
        <PageToolbarActions v-model:date="selectedDate" />
      </div>
      <n-page-header
        title="赛果与预测统计"
        :subtitle="subtitle"
        class="fa-page-toolbar-header"
      >
        <template #extra>
          <PageToolbarSearch v-model="teamSearch" />
        </template>
      </n-page-header>
    </n-layout-header>

    <!-- 主体：左统计、右列表（桌面）；手机为统计在上、列表在下 -->
    <n-layout
      :has-sider="!isPhone"
      style="flex: 1; min-height: 0;"
      content-style="display: flex; flex-direction: column; height: 100%;"
    >
      <n-layout
        content-style="display: flex; flex-direction: column; height: 100%; padding: 12px; gap: 10px; background: var(--fa-bg); box-sizing: border-box;"
      >
        <n-grid :cols="isPhone ? 1 : 2" :x-gap="10" :y-gap="10" style="flex-shrink: 0;">
          <n-gi>
            <n-card
              size="small"
              title="当日预测准确率"
              :segmented="{ content: true }"
              style="background: var(--fa-bg-elevated); height: 100%;"
            >
              <template #header-extra>
                <n-text depth="3" style="font-size: 12px;">{{ selectedDate }}</n-text>
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
                  本地库全部已预测完场，与顶部日期无关
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
              与顶部日期无关
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

        <!-- 手机：列表在下方，限高内滚动 -->
        <n-card
          v-if="isPhone"
          size="small"
          :segmented="{ content: true }"
          style="flex: 0 0 42%; min-height: 0; display: flex; flex-direction: column; background: var(--fa-bg-elevated);"
          content-style="flex: 1; min-height: 0; padding: 0;"
        >
          <template #header>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%;">
              <span>{{ listTitle }}</span>
              <ResultsFilterTrigger
                :league-options="leagueOptions"
                :selected-league-ids="filterLeagueIds"
                :selected-hit-keys="filterHitKeys"
                :filter-active="filterActive"
                @confirm="confirmFilter"
              />
            </div>
          </template>
          <div ref="phoneListShellRef" class="results-list-shell phone">
            <n-scrollbar
              style="max-height: 100%; height: 100%;"
              trigger="hover"
            >
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
                          {{ fx.home_team_name }}
                          <ScoreDetailLink
                            :label="resultScoreText(fx)"
                            @click="goDetail(fx.fixture_id)"
                          />
                          {{ fx.away_team_name }}
                          <n-text
                            v-if="resultExtraScoreLine(fx)"
                            depth="3"
                            style="display: block; font-size: 11px; font-weight: 400;"
                          >
                            {{ resultExtraScoreLine(fx) }}
                          </n-text>
                        </template>
                        <ResultHitTags :fixture="fx" />
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

      <!-- 右侧：赛果列表（桌面唯一滚动区） -->
      <n-layout-sider
        v-if="!isPhone"
        placement="right"
        bordered
        :width="440"
        :native-scrollbar="true"
        content-style="height: 100%; overflow: hidden; display: flex; flex-direction: column; background: var(--fa-bg-elevated); box-sizing: border-box;"
      >
        <div
          style="padding: 10px 12px 6px; flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; gap: 8px;"
        >
          <n-text strong>{{ listTitle }}</n-text>
          <ResultsFilterTrigger
            :league-options="leagueOptions"
            :selected-league-ids="filterLeagueIds"
            :selected-hit-keys="filterHitKeys"
            :filter-active="filterActive"
            @confirm="confirmFilter"
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
                            {{ leagueNameZh(fx.league_name) }}
                          </n-tag>
                          <span style="font-size: 12px; color: var(--fa-text-secondary);">
                            {{ formatDateTime(fx.fixture_date) }}
                          </span>
                        </n-space>
                      </template>
                      <template #header-extra>
                        <n-tag
                          size="small"
                          :type="resultStatusTagType(fx.status, fx.status_short)"
                          :bordered="false"
                        >
                          {{ statusLabel(fx.status, fx.status_short) }}
                        </n-tag>
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
  </n-layout>
  </div>
</template>

<style scoped>
.results-layout {
  height: 100%;
  overflow: hidden;
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
