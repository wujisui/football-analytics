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
import { formatDateTime, statusLabel, statusTagType } from '@/utils/format'
import { leagueNameZh } from '@/utils/leagueNames'
import { teamNameZh } from '@/utils/teamNames'

const HISTORY_DAYS = 30
const isPhone = useIsPhone()
const message = useMessage()
const { cooldownLeft, inCooldown, cooldownHint, applySyncResult } = useSyncCooldown()

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

const emptyText = computed(() =>
  selectedDate.value
    ? `${selectedDate.value} 暂无已结束赛果（可点「同步赛果」从官方回写）`
    : '请选择日期',
)

const subtitle = computed(() => {
  if (inCooldown.value) return cooldownHint.value
  const base = '左列表 · 右准确率（默认昨天）'
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

const listTitle = computed(() => `赛果列表 · ${selectedDate.value}`)

function scoreText(fx: ResultFixture): string {
  if (fx.home_goals == null || fx.away_goals == null) return '—'
  return `${fx.home_goals} : ${fx.away_goals}`
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
    history.value = await fetchResultsHistory({ days: HISTORY_DAYS })
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
  if (!selectedDate.value) return
  if (inCooldown.value) {
    message.warning(cooldownHint.value || `请稍后再试（剩余 ${cooldownLeft.value} 秒）`)
    return
  }
  syncing.value = true
  error.value = ''
  hint.value = '正在同步…'
  try {
    const result = await syncFixtures({
      date: selectedDate.value,
      includeResults: true,
    })
    if (applySyncResult(result)) {
      hint.value = cooldownHint.value || result.message
      message.warning(hint.value)
      return
    }
    hint.value = result.message
    message.success(result.message || '同步完成')
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
        <n-space :size="8" align="center">
          <n-date-picker
            v-model:formatted-value="selectedDate"
            value-format="yyyy-MM-dd"
            type="date"
            size="small"
            @update:formatted-value="onDateChange"
          />
          <n-button size="small" :loading="loading" @click="loadDayResults">查询</n-button>
          <n-button
            size="small"
            type="primary"
            :loading="syncing"
            :disabled="syncing || inCooldown"
            :title="inCooldown ? cooldownHint : '同步当日赛果'"
            @click="syncDay"
          >
            {{ inCooldown ? `冷却中 ${cooldownLeft}s` : '同步赛果' }}
          </n-button>
        </n-space>
      </n-space>
      <n-alert
        v-if="inCooldown"
        type="warning"
        :title="cooldownHint"
        :bordered="false"
        style="margin-top: 8px;"
      />
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
        <div style="padding: 10px 12px 6px; flex-shrink: 0;">
          <n-text strong>{{ listTitle }}</n-text>
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
                v-if="!loading && !fixtures.length"
                :description="emptyText"
                style="padding: 40px 12px;"
              />
              <n-list v-else style="background: transparent;">
                <n-list-item v-for="fx in fixtures" :key="fx.fixture_id">
                  <n-thing>
                    <template #header>
                      <n-space :size="6" align="center" wrap>
                        <n-tag size="small" :bordered="false">
                          {{ leagueNameZh(fx.league_name) }}
                        </n-tag>
                        <span style="font-size: 12px; color: var(--fa-text-secondary);">
                          {{ formatDateTime(fx.fixture_date) }}
                        </span>
                      </n-space>
                    </template>
                    <template #header-extra>
                      <n-tag size="small" :type="statusTagType(fx.status)" :bordered="false">
                        {{ statusLabel(fx.status) }}
                      </n-tag>
                    </template>
                    <n-grid :cols="3" :x-gap="8" style="align-items: center; font-weight: 600;">
                      <n-gi style="text-align: right; font-size: 13px;">
                        {{ teamNameZh(fx.home_team_name, fx.home_team_id) }}
                      </n-gi>
                      <n-gi style="text-align: center; font-variant-numeric: tabular-nums;">
                        {{ scoreText(fx) }}
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
          :title="listTitle"
          :segmented="{ content: true }"
          style="flex: 0 0 42%; min-height: 0; display: flex; flex-direction: column; background: var(--fa-bg-elevated);"
          content-style="flex: 1; min-height: 0; padding: 0;"
        >
          <n-scrollbar style="max-height: 100%;" trigger="hover">
            <div style="padding: 8px 12px 12px;">
              <n-spin :show="loading || syncing">
                <n-empty
                  v-if="!loading && !fixtures.length"
                  :description="emptyText"
                  style="padding: 24px 12px;"
                />
                <n-list v-else>
                  <n-list-item v-for="fx in fixtures" :key="fx.fixture_id">
                    <n-thing>
                      <template #header>
                        {{ teamNameZh(fx.home_team_name, fx.home_team_id) }}
                        {{ scoreText(fx) }}
                        {{ teamNameZh(fx.away_team_name, fx.away_team_id) }}
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
                    <n-statistic label="胜平负" :value="formatRate(dayAccuracy?.result)" />
                  </n-gi>
                  <n-gi>
                    <n-statistic label="比分" :value="formatRate(dayAccuracy?.score)" />
                  </n-gi>
                  <n-gi>
                    <n-statistic label="大小球" :value="formatRate(dayAccuracy?.ou)" />
                  </n-gi>
                  <n-gi>
                    <n-statistic label="双方进球" :value="formatRate(dayAccuracy?.btts)" />
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
