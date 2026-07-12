<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'

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
import { useIsPhone } from '@/composables/useMediaQuery'
import { useSyncCooldown } from '@/composables/useSyncCooldown'
import { formatDateTime, leagueTagColor, statusLabel, statusTagType } from '@/utils/format'
import { leagueNameZh } from '@/utils/leagueNames'
import { teamNameZh } from '@/utils/teamNames'

const HISTORY_DAYS = 30
const isPhone = useIsPhone()
const message = useMessage()
const { cooldownLeft, inCooldown, applySyncResult } = useSyncCooldown()

function localISODate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function yesterdayLocalISO(): string {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return localISODate(d)
}

const selectedDate = ref(yesterdayLocalISO())
const fixtures = ref<ResultFixture[]>([])
const dayAccuracy = ref<ResultsAccuracy | null>(null)
const history = ref<ResultsHistoryResponse | null>(null)
const loading = ref(false)
const historyLoading = ref(false)
const syncing = ref(false)
const error = ref('')
const hint = ref('')

/** Filters applied to list (confirmed from popover). */
const filterLeagueId = ref<number | 'all'>('all')
const filterHit = ref<'all' | 'result' | 'score' | 'ou' | 'btts'>('all')
/** Draft values inside the list-header filter popover. */
const draftLeagueId = ref<number | 'all'>('all')
const draftHit = ref<'all' | 'result' | 'score' | 'ou' | 'btts'>('all')
const filterOpen = ref(false)

const leagueOptions = computed(() => {
  const map = new Map<number, string>()
  for (const fx of fixtures.value) {
    if (!map.has(fx.league_id)) {
      map.set(fx.league_id, leagueNameZh(fx.league_name))
    }
  }
  return [
    { label: '全部联赛', value: 'all' as const },
    ...[...map.entries()]
      .sort((a, b) => a[1].localeCompare(b[1], 'zh'))
      .map(([id, name]) => ({ label: name, value: id })),
  ]
})

const hitOptions = [
  { label: '全部结果', value: 'all' },
  { label: '胜平负命中', value: 'result' },
  { label: '比分命中', value: 'score' },
  { label: '大小球命中', value: 'ou' },
  { label: '双方进球命中', value: 'btts' },
]

const filterActive = computed(
  () => filterLeagueId.value !== 'all' || filterHit.value !== 'all',
)

function openFilterPopover(show: boolean) {
  filterOpen.value = show
  if (show) {
    draftLeagueId.value = filterLeagueId.value
    draftHit.value = filterHit.value
  }
}

function resetFilterDraft() {
  draftLeagueId.value = 'all'
  draftHit.value = 'all'
}

function confirmFilter() {
  filterLeagueId.value = draftLeagueId.value
  filterHit.value = draftHit.value
  filterOpen.value = false
}

const filteredFixtures = computed(() => {
  let list = fixtures.value
  if (filterLeagueId.value !== 'all') {
    list = list.filter((fx) => fx.league_id === filterLeagueId.value)
  }
  if (filterHit.value === 'result') {
    list = list.filter((fx) => fx.result_hit === true)
  } else if (filterHit.value === 'score') {
    list = list.filter((fx) => fx.score_hit === true)
  } else if (filterHit.value === 'ou') {
    list = list.filter((fx) => fx.ou_hit === true)
  } else if (filterHit.value === 'btts') {
    list = list.filter((fx) => fx.btts_hit === true)
  }
  return list
})

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
  const filtered = filterLeagueId.value !== 'all' || filterHit.value !== 'all'
  if (!filtered) return dayAccuracy.value
  return summarizeFiltered(filteredFixtures.value)
})

const emptyText = computed(() => {
  if (!selectedDate.value) return '请选择日期'
  if (fixtures.value.length && !filteredFixtures.value.length) {
    return '当前筛选下无场次，可调整联赛 / 命中维度'
  }
  return `${selectedDate.value} 暂无已结束赛果（可点「同步赛果」从官方回写）`
})

const subtitle = computed(() => {
  const base = '常规时间对照预测 · 加时/点球单独标注'
  return hint.value ? `${base} · ${hint.value}` : base
})

const historyRangeLabel = computed(() => {
  if (!history.value) return `近 ${HISTORY_DAYS} 日汇总`
  if (!history.value.series.length) return `近 ${HISTORY_DAYS} 日 · 暂无预测样本`
  return `${history.value.start_date} ~ ${history.value.end_date}`
})

const hasChartData = computed(
  () => (history.value?.series ?? []).some((p) => p.fixtures_with_prediction > 0),
)

const listTitle = computed(() => {
  const n = filteredFixtures.value.length
  const total = fixtures.value.length
  if (total && n !== total) return `赛果列表 · ${selectedDate.value}（${n}/${total}）`
  return `赛果列表 · ${selectedDate.value}`
})

/** Main board = regulation 90'. */
function scoreText(fx: ResultFixture): string {
  if (fx.home_goals == null || fx.away_goals == null) return '—'
  return `${fx.home_goals} : ${fx.away_goals}`
}

/** One line under main score: 加时：a-b；点球：c-d */
function extraScoreLine(fx: ResultFixture): string | null {
  const parts: string[] = []
  const et = etScoreText(fx)
  const pen = penScoreText(fx)
  if (et) parts.push(`加时：${et}`)
  if (pen) parts.push(`点球：${pen}`)
  return parts.length ? parts.join('；') : null
}

function etScoreText(fx: ResultFixture): string | null {
  if (fx.et_home_goals == null || fx.et_away_goals == null) return null
  return `${fx.et_home_goals}-${fx.et_away_goals}`
}

function penScoreText(fx: ResultFixture): string | null {
  if (fx.pen_home == null || fx.pen_away == null) return null
  return `${fx.pen_home}-${fx.pen_away}`
}

function formatRate(stat: AccuracyStat | undefined): string {
  if (!stat || stat.total <= 0 || stat.rate == null) return '—'
  return `${(stat.rate * 100).toFixed(0)}%（${stat.hits}/${stat.total}）`
}

function hitTagType(hit: boolean | null | undefined): 'success' | 'error' | 'default' {
  if (hit === true) return 'success'
  if (hit === false) return 'error'
  return 'default'
}

function hitLabel(hit: boolean | null | undefined): string {
  if (hit === true) return '中'
  if (hit === false) return '未中'
  return '—'
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
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载失败'
    fixtures.value = []
    dayAccuracy.value = null
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    history.value = await fetchResultsHistory({
      days: HISTORY_DAYS,
      leagueId: filterLeagueId.value === 'all' ? undefined : filterLeagueId.value,
    })
  } catch {
    history.value = null
  } finally {
    historyLoading.value = false
  }
}

function onDateChange(value: string | null) {
  selectedDate.value = value || yesterdayLocalISO()
}

async function syncDay() {
  if (!selectedDate.value || inCooldown.value) return
  syncing.value = true
  error.value = ''
  hint.value = ''
  try {
    const result = await syncFixtures({
      date: selectedDate.value,
      includeResults: true,
    })
    const blocked = applySyncResult(result)
    if (blocked) return
    message.success(`刷新成功，${cooldownLeft.value} 秒后可再次刷新`)
    await Promise.all([loadDayResults(), loadHistory()])
  } catch (err) {
    error.value = err instanceof Error ? err.message : '同步失败'
    message.error(error.value)
  } finally {
    syncing.value = false
  }
}

watch(selectedDate, () => {
  void loadDayResults()
})

watch(filterLeagueId, () => {
  void loadHistory()
})

onMounted(() => {
  void loadDayResults()
  void loadHistory()
})
</script>

<template>
  <n-layout
    position="absolute"
    content-style="display: flex; flex-direction: column; height: 100%; background: var(--fa-bg);"
  >
    <n-layout-header
      bordered
      style="flex-shrink: 0; padding: 10px 16px 8px; background: var(--fa-bg-elevated);"
    >
      <n-space justify="space-between" align="center" wrap :size="8">
        <n-breadcrumb>
          <n-breadcrumb-item>赛果</n-breadcrumb-item>
          <n-breadcrumb-item>{{ selectedDate }}</n-breadcrumb-item>
        </n-breadcrumb>
        <n-space :size="8" align="center" wrap>
          <n-date-picker
            v-model:formatted-value="selectedDate"
            value-format="yyyy-MM-dd"
            type="date"
            size="small"
            @update:formatted-value="onDateChange"
          />
          <n-button
            size="small"
            type="primary"
            :loading="syncing"
            :disabled="syncing || inCooldown"
            @click="syncDay"
          >
            {{ inCooldown ? '刷新冷却中' : '同步赛果' }}
          </n-button>
        </n-space>
      </n-space>
      <n-page-header title="赛果与预测复盘" :subtitle="subtitle" style="margin-top: 4px;" />
    </n-layout-header>

    <!-- 主体固定高度：整页不滚；左列表滚，右侧面板锁在视口内 -->
    <n-layout
      :has-sider="!isPhone"
      style="flex: 1; min-height: 0;"
      content-style="display: flex; flex-direction: column; height: 100%;"
    >
      <!-- 左侧：赛果列表（唯一滚动区） -->
      <n-layout-sider
        v-if="!isPhone"
        bordered
        :width="440"
        :native-scrollbar="true"
        content-style="height: 100%; overflow: hidden; display: flex; flex-direction: column; background: var(--fa-bg-elevated); box-sizing: border-box;"
      >
        <div
          style="padding: 10px 12px 6px; flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; gap: 8px;"
        >
          <n-text strong>{{ listTitle }}</n-text>
          <n-popover
            :show="filterOpen"
            trigger="click"
            placement="bottom-end"
            :show-arrow="false"
            @update:show="openFilterPopover"
          >
            <template #trigger>
              <n-button
                size="tiny"
                quaternary
                :type="filterActive ? 'primary' : 'default'"
                aria-label="筛选赛果"
              >
                <template #icon>
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    width="14"
                    height="14"
                    fill="currentColor"
                    aria-hidden="true"
                  >
                    <path d="M3 5h18l-7 8v5l-4 2v-7L3 5z" />
                  </svg>
                </template>
                筛选
              </n-button>
            </template>
            <div style="width: 200px; display: flex; flex-direction: column; gap: 10px;">
              <n-select
                v-model:value="draftLeagueId"
                :options="leagueOptions"
                size="small"
                :consistent-menu-width="false"
              />
              <n-select
                v-model:value="draftHit"
                :options="hitOptions"
                size="small"
              />
              <n-space justify="end" :size="8">
                <n-button size="tiny" @click="resetFilterDraft">重置</n-button>
                <n-button size="tiny" type="primary" @click="confirmFilter">确认</n-button>
              </n-space>
            </div>
          </n-popover>
        </div>
        <n-alert
          v-if="error"
          type="error"
          :title="error"
          style="margin: 0 12px 8px; flex-shrink: 0;"
        >
          <n-button size="small" type="primary" @click="loadDayResults">重试</n-button>
        </n-alert>
        <n-scrollbar style="flex: 1; min-height: 0;" trigger="hover">
          <div style="padding: 4px 14px 16px;">
            <n-spin :show="loading || syncing">
              <n-empty
                v-if="!loading && !filteredFixtures.length"
                :description="emptyText"
                style="padding: 40px 12px;"
              />
              <n-list v-else style="background: transparent;">
                <n-list-item v-for="fx in filteredFixtures" :key="fx.fixture_id">
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
                        :type="statusTagType(fx.status, fx.status_short)"
                        :bordered="false"
                      >
                        {{ statusLabel(fx.status, fx.status_short) }}
                      </n-tag>
                    </template>
                    <n-grid :cols="3" :x-gap="8" style="align-items: center; font-weight: 600;">
                      <n-gi style="text-align: right; font-size: 13px;">
                        {{ teamNameZh(fx.home_team_name, fx.home_team_id) }}
                      </n-gi>
                      <n-gi style="text-align: center; font-variant-numeric: tabular-nums;">
                        <div>{{ scoreText(fx) }}</div>
                        <div
                          v-if="extraScoreLine(fx)"
                          style="font-size: 11px; font-weight: 500; color: var(--fa-text-secondary); margin-top: 2px;"
                        >
                          {{ extraScoreLine(fx) }}
                        </div>
                      </n-gi>
                      <n-gi style="font-size: 13px;">
                        {{ teamNameZh(fx.away_team_name, fx.away_team_id) }}
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
                    <n-space :size="6" wrap>
                      <n-tag size="small" :type="hitTagType(fx.result_hit)" :bordered="false">
                        胜平负 {{ hitLabel(fx.result_hit) }}
                      </n-tag>
                      <n-tag size="small" :type="hitTagType(fx.score_hit)" :bordered="false">
                        比分 {{ hitLabel(fx.score_hit) }}
                      </n-tag>
                      <n-tag size="small" :type="hitTagType(fx.ou_hit)" :bordered="false">
                        大小 {{ hitLabel(fx.ou_hit) }}
                      </n-tag>
                      <n-tag size="small" :type="hitTagType(fx.btts_hit)" :bordered="false">
                        双方进球 {{ hitLabel(fx.btts_hit) }}
                      </n-tag>
                    </n-space>
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
      </n-layout-sider>

      <!-- 右侧：当日 / 历史 / 图表（不滚，压缩适配高度） -->
      <n-layout
        content-style="display: flex; flex-direction: column; height: 100%; padding: 12px; gap: 10px; background: var(--fa-bg); box-sizing: border-box;"
      >
        <!-- 手机：列表放上方，限高内滚动 -->
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
              <n-popover
                :show="filterOpen"
                trigger="click"
                placement="bottom-end"
                :show-arrow="false"
                @update:show="openFilterPopover"
              >
                <template #trigger>
                  <n-button
                    size="tiny"
                    quaternary
                    :type="filterActive ? 'primary' : 'default'"
                    aria-label="筛选赛果"
                  >
                    筛选
                  </n-button>
                </template>
                <div style="width: 200px; display: flex; flex-direction: column; gap: 10px;">
                  <n-select
                    v-model:value="draftLeagueId"
                    :options="leagueOptions"
                    size="small"
                    :consistent-menu-width="false"
                  />
                  <n-select
                    v-model:value="draftHit"
                    :options="hitOptions"
                    size="small"
                  />
                  <n-space justify="end" :size="8">
                    <n-button size="tiny" @click="resetFilterDraft">重置</n-button>
                    <n-button size="tiny" type="primary" @click="confirmFilter">确认</n-button>
                  </n-space>
                </div>
              </n-popover>
            </div>
          </template>
          <n-scrollbar style="max-height: 100%;" trigger="hover">
            <div style="padding: 8px 12px 12px;">
              <n-spin :show="loading || syncing">
                <n-empty
                  v-if="!loading && !filteredFixtures.length"
                  :description="emptyText"
                  style="padding: 24px 12px;"
                />
                <n-list v-else>
                  <n-list-item v-for="fx in filteredFixtures" :key="fx.fixture_id">
                    <n-thing>
                      <template #header>
                        {{ teamNameZh(fx.home_team_name, fx.home_team_id) }}
                        {{ scoreText(fx) }}
                        {{ teamNameZh(fx.away_team_name, fx.away_team_id) }}
                        <n-text
                          v-if="extraScoreLine(fx)"
                          depth="3"
                          style="display: block; font-size: 11px; font-weight: 400;"
                        >
                          {{ extraScoreLine(fx) }}
                        </n-text>
                      </template>
                      <n-space v-if="fx.has_prediction" :size="6" wrap>
                        <n-tag size="small" :type="hitTagType(fx.result_hit)" :bordered="false">
                          胜平负 {{ hitLabel(fx.result_hit) }}
                        </n-tag>
                        <n-tag size="small" :type="hitTagType(fx.score_hit)" :bordered="false">
                          比分 {{ hitLabel(fx.score_hit) }}
                        </n-tag>
                        <n-tag size="small" :type="hitTagType(fx.ou_hit)" :bordered="false">
                          大小 {{ hitLabel(fx.ou_hit) }}
                        </n-tag>
                        <n-tag size="small" :type="hitTagType(fx.btts_hit)" :bordered="false">
                          双方进球 {{ hitLabel(fx.btts_hit) }}
                        </n-tag>
                      </n-space>
                    </n-thing>
                  </n-list-item>
                </n-list>
              </n-spin>
            </div>
          </n-scrollbar>
        </n-card>

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
              <n-spin :show="loading">
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
                <n-text depth="3" style="font-size: 12px;">{{ historyRangeLabel }}</n-text>
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
            <n-text depth="3" style="font-size: 12px;">仅含有预测样本的日期</n-text>
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
      </n-layout>
    </n-layout>
  </n-layout>
</template>

<style scoped>
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
