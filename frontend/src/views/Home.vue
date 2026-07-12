<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'

import FixtureList from '@/components/FixtureList.vue'
import LeagueMenu from '@/components/LeagueMenu.vue'
import { syncFixtures } from '@/api/fixtures'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import { useIsPhone, useIsTabletDown } from '@/composables/useMediaQuery'
import { useSyncCooldown } from '@/composables/useSyncCooldown'
import { parseApiDate } from '@/utils/format'
import { leagueNameZh } from '@/utils/leagueNames'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const isPhone = useIsPhone()
const isTabletDown = useIsTabletDown()

const {
  LOOKAHEAD_DAYS,
  homeWindowDays,
  homeWindowStartDate,
  leagues,
  allFixtures,
  windowLabel,
  loading,
  error,
  loadHomeFixtures,
} = useHomeFixtures()

const { cooldownLeft, inCooldown, cooldownHint, applySyncResult } = useSyncCooldown()

/** null = 全部联赛 */
const selectedLeagueId = ref<number | null>(null)
const siderCollapsed = ref(false)
const leagueDrawerShow = ref(false)
const syncing = ref(false)
const syncHint = ref('')

const refreshDisabled = computed(() => loading.value || syncing.value || inCooldown.value)
const refreshLabel = computed(() =>
  inCooldown.value ? `冷却中 ${cooldownLeft.value}s` : '强制刷新',
)

const selectedLeague = computed(() =>
  selectedLeagueId.value == null
    ? null
    : (leagues.value.find((l) => l.league_id === selectedLeagueId.value) ?? null),
)

const ACTIVE_STATUSES = new Set(['pending', 'live'])

function isActiveFixture(status: string): boolean {
  return ACTIVE_STATUSES.has(status.toLowerCase())
}

const pendingCountByLeague = computed(() => {
  const map = new Map<number, number>()
  for (const f of allFixtures.value) {
    if (!isActiveFixture(f.status)) continue
    map.set(f.league_id, (map.get(f.league_id) || 0) + 1)
  }
  return map
})

const totalPending = computed(() =>
  allFixtures.value.filter((f) => isActiveFixture(f.status)).length,
)

const displayedFixtures = computed(() => {
  let list = allFixtures.value.filter((f) => isActiveFixture(f.status))
  if (selectedLeagueId.value != null) {
    list = list.filter((f) => f.league_id === selectedLeagueId.value)
  }
  return list
    .slice()
    .sort(
      (a, b) =>
        parseApiDate(a.fixture_date).getTime() -
        parseApiDate(b.fixture_date).getTime(),
    )
})

const emptyText = computed(() => {
  if (selectedLeagueId.value == null) {
    return `近 ${LOOKAHEAD_DAYS} 日暂无未完赛赛事`
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

function syncLeagueFromRoute() {
  const fromQuery = route.query.league
  if (fromQuery === 'all' || fromQuery == null || fromQuery === '') {
    selectedLeagueId.value = null
    return
  }
  const id = Number(fromQuery)
  selectedLeagueId.value =
    !Number.isNaN(id) && leagues.value.some((l) => l.league_id === id) ? id : null
}

async function loadAll(force = false) {
  try {
    await loadHomeFixtures({ force })
    syncLeagueFromRoute()
  } catch {
    // error already set in composable
  }
}

/** Force pull from official API into local DB, then reload list. */
async function forceRefresh() {
  if (inCooldown.value) {
    message.warning(cooldownHint.value || `请稍后再试（剩余 ${cooldownLeft.value} 秒）`)
    return
  }
  syncing.value = true
  syncHint.value = '正在强制同步赛程与盘口…'
  try {
    const result = await syncFixtures({
      days: homeWindowDays(),
      date: homeWindowStartDate(),
      includeResults: true,
    })
    if (applySyncResult(result)) {
      syncHint.value = cooldownHint.value || result.message
      message.warning(syncHint.value)
      return
    }
    syncHint.value = result.message
    message.success(result.message || '同步完成')
    await loadAll(true)
  } catch (err) {
    syncHint.value = err instanceof Error ? err.message : '同步失败'
    message.error(syncHint.value)
    // Still try a local reload so the UI is not stuck.
    await loadAll(true)
  } finally {
    syncing.value = false
  }
}

function selectLeague(leagueId: number | null) {
  selectedLeagueId.value = leagueId
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

onMounted(() => {
  // Full browser refresh should not reuse the 5‑min in-memory list (stale picks).
  void loadAll(true)
})
</script>

<template>
  <n-layout :has-sider="!isPhone" class="home-layout" position="absolute">
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
        :leagues="leagues"
        :selected-league-id="selectedLeagueId"
        :pending-count-by-league="pendingCountByLeague"
        :total-pending="totalPending"
        :loading="loading"
        :collapsed="siderCollapsed"
        @select="selectLeague"
      />
    </n-layout-sider>

    <n-layout
      class="home-main"
      content-style="display: flex; flex-direction: column; height: 100%;"
    >
      <n-layout-header bordered class="home-toolbar" style="flex-shrink: 0;">
        <div class="toolbar-top">
          <n-button
            type="primary"
            size="small"
            class="league-trigger"
            @click="leagueDrawerShow = true"
          >
            联赛筛选
          </n-button>
          <n-breadcrumb class="crumb">
            <n-breadcrumb-item @click="selectLeague(null)">赛前赛事</n-breadcrumb-item>
            <n-breadcrumb-item>{{ breadcrumbFilter }}</n-breadcrumb-item>
          </n-breadcrumb>
          <n-button
            size="small"
            quaternary
            class="refresh-btn"
            :loading="syncing"
            :disabled="refreshDisabled"
            :title="inCooldown ? cooldownHint : '从官方强制同步赛程与盘口到本地'"
            @click="forceRefresh"
          >
            {{ refreshLabel }}
          </n-button>
        </div>

        <n-alert
          v-if="inCooldown"
          type="warning"
          :title="cooldownHint"
          class="cooldown-alert"
          :bordered="false"
        >
          冷却是为了避免短时间重复打官方接口、耗尽免费配额。倒计时结束后即可再次强制刷新。
        </n-alert>

        <n-page-header :title="listTitle" class="page-header">
          <template #subtitle>
            未完赛 {{ displayedFixtures.length }} 场
            <template v-if="windowLabel"> · {{ windowLabel }}</template>
            <span class="desktop-only"> · 数据来自本地库</span>
            <template v-if="syncHint && !inCooldown"> · {{ syncHint }}</template>
          </template>
        </n-page-header>
      </n-layout-header>

      <n-layout-content
        class="home-content"
        :native-scrollbar="false"
        :scrollbar-props="{ trigger: 'hover' }"
        :content-style="
          isPhone ? 'padding: 12px 12px 20px;' : 'padding: 16px 20px 24px;'
        "
        style="flex: 1; min-height: 0;"
      >
        <n-alert v-if="error" type="error" :title="error" class="state">
          <n-button size="small" type="primary" @click="loadAll(true)">重试</n-button>
        </n-alert>

        <n-spin v-else :show="loading">
          <div class="spin-body">
            <FixtureList
              v-if="!loading || allFixtures.length"
              :fixtures="displayedFixtures"
              :empty-description="emptyText"
            />
          </div>
        </n-spin>
      </n-layout-content>
    </n-layout>
  </n-layout>

  <n-drawer
    v-model:show="leagueDrawerShow"
    placement="left"
    :width="300"
    to="body"
    display-directive="show"
  >
    <n-drawer-content title="联赛筛选" closable :native-scrollbar="false">
      <LeagueMenu
        :leagues="leagues"
        :selected-league-id="selectedLeagueId"
        :pending-count-by-league="pendingCountByLeague"
        :total-pending="totalPending"
        :loading="loading"
        :collapsed="false"
        @select="selectLeague"
      />
    </n-drawer-content>
  </n-drawer>
</template>

<style scoped>
.home-layout {
  inset: 0;
  background: var(--fa-bg);
}

.home-main {
  background: var(--fa-bg);
  min-width: 0;
}

.home-toolbar {
  height: auto;
  padding: 10px 12px 8px;
  background: var(--fa-bg-elevated);
  flex-shrink: 0;
}

.cooldown-alert {
  margin: 8px 0 0;
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
  margin-left: auto;
}

.page-header {
  margin-top: 6px;
}

.home-content {
  flex: 1;
  min-height: 0;
  background: var(--fa-bg);
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

  .desktop-only {
    display: none;
  }

  .page-header :deep(.n-page-header__title) {
    font-size: 18px;
  }

  .page-header :deep(.n-page-header__subtitle) {
    font-size: 12px;
  }
}
</style>
