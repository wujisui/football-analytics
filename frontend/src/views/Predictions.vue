<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'

import PageToolbarActions from '@/components/PageToolbarActions.vue'
import PageToolbarSearch from '@/components/PageToolbarSearch.vue'
import FixtureList from '@/components/FixtureList.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import { syncFixtures } from '@/api/fixtures'
import { markDayAutoSynced, isDayAutoSynced, shouldAutoSyncDay } from '@/composables/useDayAutoSync'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useTrackedLeagues } from '@/composables/useTrackedLeagues'
import { parseApiDate } from '@/utils/format'
import { filterByTeamQuery, teamSearchEmptyHint } from '@/utils/teamSearch'

defineOptions({ name: 'Predictions' })

const isPhone = useIsPhone()
const message = useMessage()
const { todayDate, allFixtures, windowLabel, loading, error, loadHomeFixtures } =
  useHomeFixtures()
const { catalog, trackedIds, loadFilterOptions } = useTrackedLeagues()

const selectedDay = ref(todayDate())
const teamSearch = ref('')
const syncing = ref(false)
const listShellRef = ref<HTMLElement | null>(null)

const contentLoading = computed(() => loading.value || syncing.value)

const trackedIdSet = computed(() => new Set(trackedIds.value))
const ACTIVE_STATUSES = new Set(['pending', 'live'])

function isActiveFixture(status: string): boolean {
  return ACTIVE_STATUSES.has(status.toLowerCase())
}

const trackedFixtures = computed(() =>
  allFixtures.value.filter(
    (f) => trackedIdSet.value.has(f.league_id) && isActiveFixture(f.status),
  ),
)

const sortedFixtures = computed(() =>
  trackedFixtures.value
    .slice()
    .sort(
      (a, b) =>
        parseApiDate(a.fixture_date).getTime() -
        parseApiDate(b.fixture_date).getTime(),
    ),
)

const displayedFixtures = computed(() =>
  filterByTeamQuery(sortedFixtures.value, teamSearch.value),
)

const emptyText = computed(() => {
  if (error.value) return ''
  if (
    isDayAutoSynced(selectedDay.value) &&
    !allFixtures.value.length &&
    !contentLoading.value
  ) {
    return `${selectedDay.value} 当日没有比赛数据`
  }
  if (!trackedIds.value.length) return '请先在赛前页「筛选」中勾选联赛'
  if (!displayedFixtures.value.length && !teamSearch.value.trim()) {
    return `${selectedDay.value} 暂无未完赛预测`
  }
  const teamHint = teamSearchEmptyHint(teamSearch.value)
  if (teamHint && sortedFixtures.value.length) return teamHint
  return `${selectedDay.value} 暂无未完赛预测`
})

function leagueIdsForSync(): number[] {
  return trackedIds.value.length > 0
    ? trackedIds.value
    : catalog.value.map((l) => l.league_id)
}

async function loadDayLocal(force = false) {
  try {
    await loadHomeFixtures({ force, date: selectedDay.value, days: 1 })
  } catch {
    // error already set
  }
}

async function refreshDayData() {
  const day = selectedDay.value
  await loadDayLocal(false)

  const ids = leagueIdsForSync()
  if (!ids.length || !shouldAutoSyncDay(day, allFixtures.value.length > 0)) return

  syncing.value = true
  try {
    await syncFixtures({
      date: day,
      days: 1,
      includeResults: true,
      leagueIds: ids,
    })
    markDayAutoSynced(day)
    await loadDayLocal(true)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '获取失败')
    markDayAutoSynced(day)
    await loadDayLocal(true)
  } finally {
    syncing.value = false
  }
}

const listPad = computed(() =>
  isPhone.value ? '12px 12px 20px' : '16px 20px 24px',
)

watch(selectedDay, () => {
  void refreshDayData()
})

onMounted(async () => {
  try {
    await loadFilterOptions()
  } catch {
    // error already set
  }
  await refreshDayData()
})
</script>

<template>
  <!-- Lock height like Home: toolbar stays put; only the list scrolls. -->
  <div class="fa-page-frame">
  <n-layout
    class="pred-layout fa-page-shell"
    content-style="display: flex; flex-direction: column; height: 100%; overflow: hidden;"
  >
    <n-layout-header bordered class="fa-page-toolbar" style="flex-shrink: 0;">
      <div class="fa-toolbar-top">
        <n-breadcrumb class="fa-toolbar-crumb">
          <n-breadcrumb-item>预测</n-breadcrumb-item>
          <n-breadcrumb-item>{{ selectedDay }}</n-breadcrumb-item>
        </n-breadcrumb>
        <PageToolbarActions v-model:date="selectedDay" />
      </div>
      <n-page-header title="预测列表" class="fa-page-toolbar-header">
        <template #subtitle>
          <span v-if="windowLabel" class="window-meta">{{ windowLabel }}</span>
          <span class="window-meta">{{ displayedFixtures.length }} 场</span>
        </template>
        <template #extra>
          <PageToolbarSearch v-model="teamSearch" />
        </template>
      </n-page-header>
    </n-layout-header>

    <div ref="listShellRef" class="pred-list-shell">
      <n-scrollbar
        class="pred-list-scroll"
        trigger="hover"
        :content-style="`padding: ${listPad}; box-sizing: border-box;`"
      >
          <n-alert v-if="error" type="error" title="获取失败" class="state">
            <n-space align="center" :size="12">
              <span>{{ error }}</span>
              <n-button size="small" type="primary" @click="loadDayLocal(true)">
                重试
              </n-button>
            </n-space>
          </n-alert>
          <n-spin v-else :show="contentLoading">
            <FixtureList
              mode="prediction"
              :fixtures="displayedFixtures"
              :empty-description="emptyText"
            />
          </n-spin>
      </n-scrollbar>
      <ListBackTop :shell="listShellRef" />
    </div>
  </n-layout>
  </div>
</template>

<style scoped>
.pred-layout {
  height: 100%;
  background: var(--fa-bg);
}

.window-meta + .window-meta::before {
  content: ' · ';
  color: var(--fa-text-faint);
}

.pred-list-shell {
  flex: 1;
  min-height: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  background: var(--fa-bg);
}

.pred-list-scroll {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.state {
  margin-bottom: 12px;
}
</style>
