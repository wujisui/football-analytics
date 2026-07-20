<script setup lang="ts">
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'

import FixtureList from '@/components/FixtureList.vue'
import HomeDateStrip from '@/components/HomeDateStrip.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import PageToolbarSearch from '@/components/PageToolbarSearch.vue'

import LeagueFilterTrigger from '@/components/LeagueFilterTrigger.vue'
import LeagueMenu from '@/components/LeagueMenu.vue'
import { syncFixtures } from '@/api/fixtures'
import type { LeagueSummaryResponse } from '@/api/types'
import { markDayAutoSynced, isDayAutoSynced, shouldAutoSyncDay } from '@/composables/useDayAutoSync'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import { useIsPhone, useIsTabletDown } from '@/composables/useMediaQuery'
import { useTrackedLeagues } from '@/composables/useTrackedLeagues'
import { parseApiDate } from '@/utils/format'
import {
  readHomeLeagueFilter,
  writeHomeLeagueFilter,
} from '@/utils/homeLeagueFilter'
import { leagueNameZh } from '@/utils/leagueNames'
import { filterByTeamQuery, teamSearchEmptyHint } from '@/utils/teamSearch'
import {
  homeDayCountLabel,
  homeDayKind,
  homeDayStatusHint,
  isHomeFixtureVisible,
} from '@/utils/homeDateStrip'

defineOptions({ name: 'Home' })

const route = useRoute()
const router = useRouter()
const message = useMessage()
const isPhone = useIsPhone()
const isTabletDown = useIsTabletDown()

const {
  todayDate,
  allFixtures,
  loading,
  error,
  loadHomeFixtures,
} = useHomeFixtures()

const {
  trackedIds,
  filterOptionsError,
  setTrackedIds,
  allFilterOptions,
  loadFilterOptions,
} = useTrackedLeagues()

const selectedLeagueId = ref<number | null>(null)
/** Local calendar day `yyyy-MM-dd`; default today, sync on change. */
const selectedDay = ref(todayDate())
const teamSearch = ref('')
const siderCollapsed = ref(false)
const leagueDrawerShow = ref(false)
const syncing = ref(false)
const listShellRef = ref<HTMLElement | null>(null)

const contentLoading = computed(() => loading.value || syncing.value)

const trackedIdSet = computed(() => new Set(trackedIds.value))
const filterLeagueOptions = computed(() => allFilterOptions())
const filterOptionById = computed(
  () => new Map(filterLeagueOptions.value.map((o) => [o.league_id, o])),
)

const selectedDayKind = computed(() => homeDayKind(selectedDay.value, todayDate()))

const dayFixtures = computed(() =>
  allFixtures.value.filter(
    (f) =>
      trackedIdSet.value.has(f.league_id) &&
      isHomeFixtureVisible(f.status, selectedDay.value, todayDate()),
  ),
)

const pendingCountByLeague = computed(() => {
  const map = new Map<number, number>()
  for (const f of dayFixtures.value) {
    map.set(f.league_id, (map.get(f.league_id) || 0) + 1)
  }
  return map
})

const menuLeagues = computed((): LeagueSummaryResponse[] => {
  const map = new Map<number, LeagueSummaryResponse>()
  for (const f of dayFixtures.value) {
    const opt = filterOptionById.value.get(f.league_id)
    const count = pendingCountByLeague.value.get(f.league_id) || 0
    map.set(f.league_id, {
      league_id: f.league_id,
      league_name: opt?.league_name || f.league_name || `League ${f.league_id}`,
      country: opt?.country ?? null,
      today_fixtures_count: 0,
      upcoming_fixtures_count: count,
    })
  }
  return [...map.values()]
})

const totalPending = computed(() => dayFixtures.value.length)

const selectedLeague = computed(() => {
  if (selectedLeagueId.value == null) return null
  return menuLeagues.value.find((l) => l.league_id === selectedLeagueId.value) ?? null
})

const leagueFilteredFixtures = computed(() => {
  let list = dayFixtures.value
  if (selectedLeagueId.value != null) {
    list = list.filter((f) => f.league_id === selectedLeagueId.value)
  }
  return list
})

const sortedFixtures = computed(() =>
  leagueFilteredFixtures.value
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
  const statusHint = homeDayStatusHint(selectedDayKind.value)
  if (
    isDayAutoSynced(selectedDay.value) &&
    !allFixtures.value.length &&
    !contentLoading.value
  ) {
    return `${selectedDay.value} 当日没有比赛数据`
  }
  if (!filterLeagueOptions.value.length && !dayFixtures.value.length) {
    return '暂无匹配联赛，正在拉取配置联赛赛程…'
  }
  if (!trackedIds.value.length) {
    return '请先在「筛选」中勾选要关注的联赛'
  }
  if (!displayedFixtures.value.length && !teamSearch.value.trim()) {
    return `${selectedDay.value} 暂无${statusHint}赛事`
  }
  const teamHint = teamSearchEmptyHint(teamSearch.value)
  if (teamHint && sortedFixtures.value.length) return teamHint
  if (selectedLeagueId.value == null) {
    return `${selectedDay.value} 勾选联赛暂无${statusHint}赛事`
  }
  const name = leagueNameZh(selectedLeague.value?.league_name) || '该联赛'
  return `${selectedDay.value} 暂无${name}${statusHint}赛事`
})

const dayCountLabel = computed(() =>
  homeDayCountLabel(selectedDayKind.value, displayedFixtures.value.length),
)

const breadcrumbFilter = computed(() =>
  selectedLeague.value ? leagueNameZh(selectedLeague.value.league_name) : '全部',
)

const filterActive = computed(() => {
  const defaults = filterLeagueOptions.value
    .filter((o) => o.default_checked)
    .map((o) => o.league_id)
  if (!defaults.length && !trackedIds.value.length) return false
  if (trackedIds.value.length !== defaults.length) return true
  const tracked = trackedIdSet.value
  return defaults.some((id) => !tracked.has(id))
})

function syncLeagueFromRoute() {
  const fromQuery = route.query.league
  if (fromQuery === 'all') {
    selectedLeagueId.value = null
    writeHomeLeagueFilter(null)
    return
  }
  if (fromQuery != null && fromQuery !== '') {
    const id = Number(fromQuery)
    if (!Number.isNaN(id)) {
      selectedLeagueId.value = id
      writeHomeLeagueFilter(id)
      return
    }
  }
  // No query (e.g. header → home): restore last sidebar selection.
  const stored = readHomeLeagueFilter()
  selectedLeagueId.value = stored
  if (stored != null && route.query.league !== String(stored)) {
    void router.replace({
      name: 'home',
      query: { league: String(stored) },
    })
  }
}

function leagueIdsForSync(): number[] | undefined {
  return trackedIds.value.length ? trackedIds.value : undefined
}

async function loadDayLocal(force = false) {
  try {
    await loadHomeFixtures({ force, date: selectedDay.value, days: 1 })
    syncLeagueFromRoute()
  } catch {
    // error already set in composable
  }
}

async function runSync(
  leagueIds: number[] | undefined,
  opts?: { days?: number; date?: string },
) {
  syncing.value = true
  try {
    await syncFixtures({
      days: opts?.days ?? 1,
      date: opts?.date ?? selectedDay.value,
      includeResults: true,
      leagueIds,
    })
    markDayAutoSynced(opts?.date ?? selectedDay.value)
    await Promise.all([loadFilterOptions({ discover: true }), loadDayLocal(true)])
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

async function reloadFilterAndDay() {
  try {
    await loadFilterOptions({ date: selectedDay.value, discover: true })
  } catch {
    if (filterOptionsError.value) message.warning(filterOptionsError.value)
  }
  await refreshDayData()
}

async function confirmFilter(ids: number[]) {
  const allow = new Set(filterLeagueOptions.value.map((o) => o.league_id))
  const allowed = ids.filter((id) => allow.has(id))
  if (!allowed.length) {
    message.warning('请至少勾选一个今日有赛的联赛')
    return
  }
  setTrackedIds(allowed)
  if (
    selectedLeagueId.value != null &&
    !allowed.includes(selectedLeagueId.value)
  ) {
    selectLeague(null)
  }
  const needFetch = allowed.filter((id) => {
    const opt = filterOptionById.value.get(id)
    return !!opt && !opt.locally_loaded
  })
  if (needFetch.length) {
    await runSync(needFetch, {
      days: 1,
      date: selectedDay.value,
    })
  }
}

function selectLeague(leagueId: number | null) {
  selectedLeagueId.value = leagueId
  writeHomeLeagueFilter(leagueId)
  leagueDrawerShow.value = false
  router.replace({
    name: 'home',
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

watch(menuLeagues, () => {
  if (selectedLeagueId.value == null || !menuLeagues.value.length) return
  if (!menuLeagues.value.some((l) => l.league_id === selectedLeagueId.value)) {
    selectedLeagueId.value = null
    writeHomeLeagueFilter(null)
    if (route.query.league) {
      void router.replace({ name: 'home', query: {} })
    }
  }
})

watch(
  () => route.query.league,
  () => {
    if (route.name !== 'home') return
    syncLeagueFromRoute()
  },
)

watch(selectedDay, () => {
  void reloadFilterAndDay()
})

onMounted(() => {
  void reloadFilterAndDay()
})

onActivated(() => {
  // keep-alive return from detail: sync ?league= without remounting (keeps scroll)
  syncLeagueFromRoute()
})
</script>

<template>
  <!-- Lock page height like Results: toolbar stays put; only the list scrolls. -->
  <div class="fa-page-frame">
  <n-layout
    :has-sider="!isPhone"
    class="home-layout fa-page-shell"
    content-style="height: 100%;"
  >
    <n-layout-sider
      v-if="!isPhone"
      v-model:collapsed="siderCollapsed"
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="232"
      :native-scrollbar="false"
      show-trigger="bar"
      content-style="height: 100%;"
    >
      <LeagueMenu
        :leagues="menuLeagues"
        :selected-league-id="selectedLeagueId"
        :pending-count-by-league="pendingCountByLeague"
        :total-pending="totalPending"
        :loading="loading"
        :collapsed="siderCollapsed"
        @select="selectLeague"
      >
        <template #filter>
          <LeagueFilterTrigger
            :options="filterLeagueOptions"
            :tracked-ids="trackedIds"
            :icon-only="siderCollapsed"
            :filter-active="filterActive"
            :confirming="syncing"
            @confirm="confirmFilter"
          />
        </template>
      </LeagueMenu>
    </n-layout-sider>

    <n-layout
      class="home-main"
      style="height: 100%; flex: 1; min-height: 0; min-width: 0;"
      content-style="display: flex; flex-direction: column; height: 100%; overflow: hidden;"
    >
      <n-layout-header bordered class="fa-page-toolbar" style="flex-shrink: 0;">
        <div class="fa-toolbar-top">
          <n-button
            v-if="isPhone"
            size="small"
            secondary
            class="league-trigger"
            @click="leagueDrawerShow = true"
          >
            联赛
          </n-button>
          <n-breadcrumb class="fa-toolbar-crumb">
            <n-breadcrumb-item @click="selectLeague(null)">赛前赛事</n-breadcrumb-item>
            <n-breadcrumb-item>{{ breadcrumbFilter }}</n-breadcrumb-item>
          </n-breadcrumb>
        </div>

        <HomeDateStrip v-model="selectedDay" />

        <div class="home-list-meta">
          <span class="day-stat">{{ dayCountLabel }}</span>
          <PageToolbarSearch v-model="teamSearch" />
        </div>
      </n-layout-header>

      <div ref="listShellRef" class="home-content home-list-shell">
        <n-scrollbar
          class="home-list-scroll"
          trigger="hover"
          :content-style="
            isPhone
              ? 'padding: 12px 12px 20px; box-sizing: border-box;'
              : 'padding: 16px 20px 24px; box-sizing: border-box;'
          "
        >
          <n-alert v-if="error" type="error" title="获取失败" class="state">
            <n-space align="center" :size="12">
              <span>{{ error }}</span>
              <n-button size="small" type="primary" @click="loadDayLocal(true)">重试</n-button>
            </n-space>
          </n-alert>

          <n-spin v-else :show="contentLoading">
            <div class="spin-body">
              <FixtureList
                :fixtures="displayedFixtures"
                :empty-description="emptyText"
                :group-by-day="false"
              />
            </div>
          </n-spin>
        </n-scrollbar>
        <ListBackTop :shell="listShellRef" />
      </div>
    </n-layout>
  </n-layout>

  <n-drawer
    v-if="isPhone"
    v-model:show="leagueDrawerShow"
    placement="left"
    width="88%"
    to="body"
    display-directive="show"
    class="league-drawer"
  >
    <n-drawer-content title="联赛" closable :native-scrollbar="false" body-content-style="padding: 0; height: 100%; display: flex; flex-direction: column;">
      <LeagueMenu
        :leagues="menuLeagues"
        :selected-league-id="selectedLeagueId"
        :pending-count-by-league="pendingCountByLeague"
        :total-pending="totalPending"
        :loading="loading"
        :collapsed="false"
        @select="selectLeague"
      >
        <template #filter>
          <LeagueFilterTrigger
            drawer-mode
            :options="filterLeagueOptions"
            :tracked-ids="trackedIds"
            :filter-active="filterActive"
            :confirming="syncing"
            @confirm="confirmFilter"
          />
        </template>
      </LeagueMenu>
    </n-drawer-content>
  </n-drawer>
  </div>
</template>

<style scoped>
.home-layout {
  height: 100%;
  overflow: hidden;
  background: var(--fa-bg);
}

.home-main {
  background: var(--fa-bg);
  min-width: 0;
  overflow: hidden;
}

.league-trigger {
  flex-shrink: 0;
}

:deep(.league-drawer .n-drawer-body-content-wrapper) {
  height: 100%;
}

:deep(.league-drawer .league-menu) {
  height: 100%;
}

.home-list-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 0 4px;
}

.day-stat {
  font-size: 13px;
  color: var(--fa-text-secondary);
  white-space: nowrap;
}

.home-content {
  flex: 1;
  min-height: 0;
  background: var(--fa-bg);
}

.home-list-shell {
  position: relative;
  display: flex;
  flex-direction: column;
}

.home-list-scroll {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.spin-body {
  min-height: 200px;
}

.state {
  margin-bottom: 12px;
}

:deep(.n-breadcrumb-item:first-child .n-breadcrumb-item__link) {
  cursor: pointer;
}
</style>
