<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchResults, syncFixtures, type ResultFixture } from '@/api/fixtures'
import { useIsPhone } from '@/composables/useMediaQuery'
import { formatDateTime, statusLabel, statusTagType } from '@/utils/format'
import { leagueNameZh } from '@/utils/leagueNames'
import { teamNameZh } from '@/utils/teamNames'

const isPhone = useIsPhone()

function todayLocalISO(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const selectedDate = ref(todayLocalISO())
const fixtures = ref<ResultFixture[]>([])
const loading = ref(false)
const syncing = ref(false)
const error = ref('')
const hint = ref('')

const emptyText = computed(() =>
  selectedDate.value
    ? `${selectedDate.value} 暂无已结束赛果（可点「同步赛果」从官方回写）`
    : '请选择日期',
)

function scoreText(fx: ResultFixture): string {
  if (fx.home_goals == null || fx.away_goals == null) return '—'
  return `${fx.home_goals} : ${fx.away_goals}`
}

async function loadResults() {
  if (!selectedDate.value) {
    fixtures.value = []
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await fetchResults(selectedDate.value)
    fixtures.value = data.fixtures
    hint.value = data.total ? `共 ${data.total} 场` : ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载失败'
    fixtures.value = []
  } finally {
    loading.value = false
  }
}

function onDateChange(value: string | null) {
  selectedDate.value = value || todayLocalISO()
  void loadResults()
}

async function syncDay() {
  if (!selectedDate.value) return
  syncing.value = true
  error.value = ''
  hint.value = ''
  try {
    const result = await syncFixtures({
      date: selectedDate.value,
      includeResults: true,
    })
    hint.value = result.message
    if (result.status === 'cooldown') {
      return
    }
    await loadResults()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '同步失败'
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  void loadResults()
})
</script>

<template>
  <n-layout class="results-layout" position="absolute">
    <n-layout-header bordered class="results-toolbar">
      <div class="toolbar-row">
        <n-breadcrumb class="crumb">
          <n-breadcrumb-item>赛果</n-breadcrumb-item>
          <n-breadcrumb-item>{{ selectedDate }}</n-breadcrumb-item>
        </n-breadcrumb>
        <div class="toolbar-actions">
          <n-date-picker
            v-model:formatted-value="selectedDate"
            value-format="yyyy-MM-dd"
            type="date"
            size="small"
            @update:formatted-value="onDateChange"
          />
          <n-button size="small" :loading="loading" @click="loadResults">查询</n-button>
          <n-button
            size="small"
            type="primary"
            :loading="syncing"
            @click="syncDay"
          >
            同步赛果
          </n-button>
        </div>
      </div>
      <n-page-header title="赛果查询" class="page-header">
        <template #subtitle>
          按开赛日查看本地已落库终场比分
          <template v-if="hint"> · {{ hint }}</template>
        </template>
      </n-page-header>
    </n-layout-header>

    <n-layout-content
      class="results-content"
      :native-scrollbar="false"
      :content-style="isPhone ? 'padding: 12px 12px 20px;' : 'padding: 16px 20px 24px;'"
    >
      <n-alert v-if="error" type="error" :title="error" class="state">
        <n-button size="small" type="primary" @click="loadResults">重试</n-button>
      </n-alert>

      <n-spin v-else :show="loading || syncing">
        <n-empty v-if="!loading && !fixtures.length" :description="emptyText" />
        <div v-else class="result-list">
          <article v-for="fx in fixtures" :key="fx.fixture_id" class="result-row">
            <div class="row-meta">
              <span class="league">{{ leagueNameZh(fx.league_name) }}</span>
              <span class="kickoff">{{ formatDateTime(fx.fixture_date) }}</span>
              <n-tag size="small" :type="statusTagType(fx.status)" :bordered="false">
                {{ statusLabel(fx.status) }}
              </n-tag>
            </div>
            <div class="row-score">
              <span class="team home">
                {{ teamNameZh(fx.home_team_name, fx.home_team_id) }}
              </span>
              <span class="score">{{ scoreText(fx) }}</span>
              <span class="team away">
                {{ teamNameZh(fx.away_team_name, fx.away_team_id) }}
              </span>
            </div>
          </article>
        </div>
      </n-spin>
    </n-layout-content>
  </n-layout>
</template>

<style scoped>
.results-layout {
  inset: 0;
}

.results-toolbar {
  padding: 10px 16px 8px;
  flex-shrink: 0;
}

.toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.crumb {
  min-width: 0;
}

.page-header {
  margin-top: 4px;
}

.state {
  margin-bottom: 12px;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-row {
  padding: 12px 14px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: var(--n-color);
}

.row-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-bottom: 8px;
  font-size: 12px;
  opacity: 0.75;
}

.row-score {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 12px;
  font-size: 15px;
  font-weight: 600;
}

.team.home {
  text-align: right;
}

.team.away {
  text-align: left;
}

.score {
  min-width: 56px;
  text-align: center;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
}

@media (max-width: 767px) {
  .results-toolbar {
    padding: 8px 12px;
  }

  .row-score {
    font-size: 14px;
    gap: 8px;
  }

  .score {
    min-width: 48px;
  }
}
</style>
