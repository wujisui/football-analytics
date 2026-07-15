<script setup lang="ts">
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'

import FixtureList from '@/components/FixtureList.vue'
import { RefreshOutline } from '@vicons/ionicons5'

import LeagueFilterTrigger from '@/components/LeagueFilterTrigger.vue'
import LeagueMenu from '@/components/LeagueMenu.vue'
import { syncFixtures } from '@/api/fixtures'
import type { LeagueSummaryResponse } from '@/api/types'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import { useIsPhone, useIsTabletDown } from '@/composables/useMediaQuery'
import { useSyncCooldown } from '@/composables/useSyncCooldown'
import { useTrackedLeagues } from '@/composables/useTrackedLeagues'
import { parseApiDate } from '@/utils/format'
import {
  readHomeLeagueFilter,
  writeHomeLeagueFilter,
} from '@/utils/homeLeagueFilter'
import { leagueNameZh } from '@/utils/leagueNames'

defineOptions({ name: 'Home' })

const route = useRoute()
const router = useRouter()
const message = useMessage()
const isPhone = useIsPhone()
const isTabletDown = useIsTabletDown()

const {
  LOOKAHEAD_DAYS,
  homeWindowDays,
  homeWindowStartDate,
  todayDate,
  allFixtures,
  windowLabel,
  loading,
  error,
  loadHomeFixtures,
} = useHomeFixtures()

const {
  cooldownLeft,
  cooldownEnabled,
  inCooldown,
  applySyncResult,
} = useSyncCooldown()
const {
  catalog,
  trackedIds,
  filterOptionsError,
  setTrackedIds,
  allFilterOptions,
  loadFilterOptions,
} = useTrackedLeagues()

const selectedLeagueId = ref<number | null>(null)
/** Local calendar day `yyyy-MM-dd`; null = all days in the home window. */
const selectedDay = ref<string | null>(null)
const siderCollapsed = ref(false)
const leagueDrawerShow = ref(false)
const syncing = ref(false)
const listShellRef = ref<HTMLElement | null>(null)

/** Scroll container for n-back-top (n-scrollbar internals). */
function listScrollListenTo(): HTMLElement {
  return (
    (listShellRef.value?.querySelector(
      '.n-scrollbar-container',
    ) as HTMLElement | null) ?? document.documentElement
  )
}

function localDayKey(dateStr: string): string {
  const d = parseApiDate(dateStr)
  if (Number.isNaN(d.getTime())) return String(dateStr).slice(0, 10)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** Disable only the refresh control — list stays interactive during sync. */
const refreshDisabled = computed(() => syncing.value || inCooldown.value)
const refreshLabel = computed(() => (inCooldown.value ? '同步冷却中' : '同步赛程'))

const trackedIdSet = computed(() => new Set(trackedIds.value))
const filterLeagueOptions = computed(() => allFilterOptions())
const filterOptionById = computed(
  () => new Map(filterLeagueOptions.value.map((o) => [o.league_id, o])),
)

const ACTIVE_STATUSES = new Set(['pending', 'live'])

function isActiveFixture(status: string): boolean {
  return ACTIVE_STATUSES.has(status.toLowerCase())
}

const trackedFixtures = computed(() =>
  allFixtures.value.filter(
    (f) => trackedIdSet.value.has(f.league_id) && isActiveFixture(f.status),
  ),
)

const pendingCountByLeague = computed(() => {
  const map = new Map<number, number>()
  for (const f of trackedFixtures.value) {
    map.set(f.league_id, (map.get(f.league_id) || 0) + 1)
  }
  return map
})

/** Left menu derived only from tracked fixtures (+ filter option names). */
const menuLeagues = computed((): LeagueSummaryResponse[] => {
  const map = new Map<number, LeagueSummaryResponse>()
  for (const f of trackedFixtures.value) {
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

const totalPending = computed(() => trackedFixtures.value.length)

const selectedLeague = computed(() => {
  if (selectedLeagueId.value == null) return null
  return menuLeagues.value.find((l) => l.league_id === selectedLeagueId.value) ?? null
})

const leagueFilteredFixtures = computed(() => {
  let list = trackedFixtures.value
  if (selectedLeagueId.value != null) {
    list = list.filter((f) => f.league_id === selectedLeagueId.value)
  }
  return list
})

const availableDayKeys = computed(() => {
  const keys = new Set<string>()
  for (const f of leagueFilteredFixtures.value) {
    keys.add(localDayKey(f.fixture_date))
  }
  return keys
})

const displayedFixtures = computed(() => {
  let list = leagueFilteredFixtures.value
  if (selectedDay.value) {
    list = list.filter((f) => localDayKey(f.fixture_date) === selectedDay.value)
  }
  return list
    .slice()
    .sort(
      (a, b) =>
        parseApiDate(a.fixture_date).getTime() -
        parseApiDate(b.fixture_date).getTime(),
    )
})

function isHomeDayDisabled(ts: number): boolean {
  const d = new Date(ts)
  const localKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return !availableDayKeys.value.has(localKey)
}

const emptyText = computed(() => {
  if (!filterLeagueOptions.value.length && !trackedFixtures.value.length) {
    return '暂无匹配联赛，可先点「同步赛程」拉取配置联赛'
  }
  if (!trackedIds.value.length) {
    return '请先在「筛选」中勾选要关注的联赛'
  }
  if (selectedDay.value && !displayedFixtures.value.length) {
    return `${selectedDay.value} 暂无未完赛赛事`
  }
  if (selectedLeagueId.value == null) {
    return `近 ${LOOKAHEAD_DAYS} 日勾选联赛暂无未完赛赛事`
  }
  const name = leagueNameZh(selectedLeague.value?.league_name) || '该联赛'
  return `近 ${LOOKAHEAD_DAYS} 日暂无${name}未完赛赛事`
})

const listTitle = computed(() =>
  selectedLeague.value ? leagueNameZh(selectedLeague.value.league_name) : '全部比赛',
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

async function loadAll(force = false) {
  try {
    await loadHomeFixtures({ force })
    syncLeagueFromRoute()
  } catch {
    // error already set in composable
  }
}

async function runSync(leagueIds: number[], opts?: { days?: number; date?: string }) {
  if (!leagueIds.length) {
    message.warning('请至少勾选一个联赛')
    return false
  }
  if (inCooldown.value) {
    message.warning(`同步冷却中，请 ${cooldownLeft.value} 秒后再试`)
    return false
  }
  syncing.value = true
  try {
    const result = await syncFixtures({
      days: opts?.days ?? homeWindowDays(),
      date: opts?.date ?? homeWindowStartDate(),
      includeResults: true,
      leagueIds,
      skipCooldown: !cooldownEnabled.value,
    })
    if (applySyncResult(result)) {
      message.warning(result.message || '同步冷却中')
      return false
    }
    message.success(result.message || `已同步 ${leagueIds.length} 个联赛`)
    await Promise.all([loadFilterOptions({ discover: true }), loadAll(true)])
    // Odds finish in a backend follow-up; refresh list once they have time to land.
    window.setTimeout(() => {
      void loadAll(true)
    }, 12_000)
    return true
  } catch (err) {
    message.error(err instanceof Error ? err.message : '同步失败')
    await loadAll(true)
    return false
  } finally {
    syncing.value = false
  }
}

async function forceRefresh() {
  const ids =
    trackedIds.value.length > 0
      ? trackedIds.value
      : catalog.value.map((l) => l.league_id)
  if (!ids.length) {
    message.warning('联赛目录为空，请检查 config/leagues.json')
    return
  }
  await runSync(ids)
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
    await runSync(needFetch, { days: 1, date: todayDate() })
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

watch(availableDayKeys, (keys) => {
  if (selectedDay.value && !keys.has(selectedDay.value)) {
    selectedDay.value = null
  }
})

onMounted(async () => {
  try {
    await loadFilterOptions({ discover: true })
  } catch {
    if (filterOptionsError.value) message.warning(filterOptionsError.value)
  }
  // force once on cold start; later remounts can reuse in-memory cache via loadAll(false)
  void loadAll(!allFixtures.value.length)
})

onActivated(() => {
  // keep-alive return from detail: sync ?league= without remounting (keeps scroll)
  syncLeagueFromRoute()
})
</script>

<template>
  <!-- Lock page height like Results: toolbar stays put; only the list scrolls. -->
  <n-layout
    :has-sider="!isPhone"
    class="home-layout"
    position="absolute"
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
      <n-layout-header bordered class="home-toolbar" style="flex-shrink: 0;">
        <div class="toolbar-top">
          <n-button
            size="small"
            secondary
            class="league-trigger"
            @click="leagueDrawerShow = true"
          >
            联赛
          </n-button>
          <n-breadcrumb class="crumb">
            <n-breadcrumb-item @click="selectLeague(null)">赛前赛事</n-breadcrumb-item>
            <n-breadcrumb-item>{{ breadcrumbFilter }}</n-breadcrumb-item>
          </n-breadcrumb>
          <n-space :size="8" align="center" class="refresh-cluster">
            <n-tooltip placement="bottom">
              <template #trigger>
                <n-switch v-model:value="cooldownEnabled" size="small">
                  <template #checked>冷却</template>
                  <template #unchecked>冷却</template>
                </n-switch>
              </template>
              {{
                cooldownEnabled
                  ? '冷却保护已开：同步后约 90 秒内不可再刷'
                  : '冷却已关：可连续同步（仍消耗官方配额）'
              }}
            </n-tooltip>
            <n-button
              type="primary"
              size="small"
              class="refresh-btn"
              :loading="syncing"
              :disabled="refreshDisabled"
              @click="forceRefresh"
            >
              <template #icon>
                <n-icon :component="RefreshOutline" :size="16" />
              </template>
              {{ refreshLabel }}
            </n-button>
          </n-space>
        </div>

        <n-page-header :title="listTitle" class="page-header">
          <template #subtitle>
            <span v-if="windowLabel" class="window-meta">{{ windowLabel }}</span>
            <span class="window-meta">未完赛 {{ displayedFixtures.length }} 场</span>
          </template>
          <template #extra>
            <n-date-picker
              v-model:formatted-value="selectedDay"
              value-format="yyyy-MM-dd"
              type="date"
              size="small"
              clearable
              placeholder="全部日期"
              :is-date-disabled="isHomeDayDisabled"
            />
          </template>
        </n-page-header>
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
          <n-alert v-if="error" type="error" :title="error" class="state">
            <n-button size="small" type="primary" @click="loadAll(true)">重试</n-button>
          </n-alert>

          <!-- Only block list on cold load; force-refresh is background sync. -->
          <n-spin v-else :show="loading && !allFixtures.length">
            <div class="spin-body">
              <FixtureList
                v-if="!loading || allFixtures.length"
                :fixtures="displayedFixtures"
                :empty-description="emptyText"
              />
            </div>
          </n-spin>
        </n-scrollbar>
        <n-back-top
          :listen-to="listScrollListenTo"
          :visibility-height="240"
          :right="20"
          :bottom="24"
        />
      </div>
    </n-layout>
  </n-layout>

  <n-drawer
    v-model:show="leagueDrawerShow"
    placement="left"
    :width="300"
    to="body"
    display-directive="show"
  >
    <n-drawer-content title="联赛" closable :native-scrollbar="false">
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
</template>

<style scoped>
.home-layout {
  inset: 0;
  height: 100%;
  overflow: hidden;
  background: var(--fa-bg);
}

.home-main {
  background: var(--fa-bg);
  min-width: 0;
  overflow: hidden;
}

.home-toolbar {
  height: auto;
  padding: 10px 12px 8px;
  background: var(--fa-bg-elevated);
  flex-shrink: 0;
  position: relative;
  z-index: 2;
}

.toolbar-top {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.league-trigger {
  display: none;
  flex-shrink: 0;
}

.crumb {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.refresh-btn {
  flex-shrink: 0;
  font-weight: 600;
}

.page-header {
  margin-top: 6px;
}

.window-meta + .window-meta::before {
  content: ' · ';
  color: var(--fa-text-faint);
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

@media (min-width: 768px) {
  .home-toolbar {
    padding: 12px 20px 8px;
  }
}

@media (max-width: 767px) {
  .league-trigger {
    display: inline-flex;
  }
}
</style>
