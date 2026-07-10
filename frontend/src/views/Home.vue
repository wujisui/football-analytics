<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import FixtureList from '@/components/FixtureList.vue'
import LeagueMenu from '@/components/LeagueMenu.vue'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import { parseApiDate } from '@/utils/format'
import { leagueNameZh } from '@/utils/leagueNames'

const route = useRoute()
const router = useRouter()

const {
  LOOKAHEAD_DAYS,
  leagues,
  allFixtures,
  windowLabel,
  loading,
  error,
  loadHomeFixtures,
} = useHomeFixtures()

/** null = 全部联赛 */
const selectedLeagueId = ref<number | null>(null)
const siderCollapsed = ref(false)

const selectedLeague = computed(() =>
  selectedLeagueId.value == null
    ? null
    : (leagues.value.find((l) => l.league_id === selectedLeagueId.value) ?? null),
)

const pendingCountByLeague = computed(() => {
  const map = new Map<number, number>()
  for (const f of allFixtures.value) {
    if (f.status.toLowerCase() !== 'pending') continue
    map.set(f.league_id, (map.get(f.league_id) || 0) + 1)
  }
  return map
})

const totalPending = computed(() =>
  allFixtures.value.filter((f) => f.status.toLowerCase() === 'pending').length,
)

const displayedFixtures = computed(() => {
  let list = allFixtures.value.filter((f) => f.status.toLowerCase() === 'pending')
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
    return `近 ${LOOKAHEAD_DAYS} 日暂无未开赛赛事`
  }
  const name = leagueNameZh(selectedLeague.value?.league_name) || '该联赛'
  return `近 ${LOOKAHEAD_DAYS} 日暂无${name}未开赛赛事`
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

function selectLeague(leagueId: number | null) {
  selectedLeagueId.value = leagueId
  router.replace({
    name: 'home',
    query: leagueId == null ? {} : { league: String(leagueId) },
  })
}

onMounted(() => {
  // Full browser refresh should not reuse the 5‑min in-memory list (stale picks).
  void loadAll(true)
})
</script>

<template>
  <n-layout has-sider class="home-layout" position="absolute">
    <n-layout-sider
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

    <n-layout class="home-main" content-style="display: flex; flex-direction: column; height: 100%;">
      <n-layout-header bordered class="home-toolbar">
        <n-breadcrumb>
          <n-breadcrumb-item @click="selectLeague(null)">赛前赛事</n-breadcrumb-item>
          <n-breadcrumb-item>{{ breadcrumbFilter }}</n-breadcrumb-item>
        </n-breadcrumb>

        <n-page-header :title="listTitle" class="page-header">
          <template #subtitle>
            未开赛 {{ displayedFixtures.length }} 场
            <template v-if="windowLabel"> · {{ windowLabel }}</template>
            · 数据来自本地库
          </template>
          <template #extra>
            <n-button size="small" quaternary :loading="loading" @click="loadAll(true)">
              刷新
            </n-button>
          </template>
        </n-page-header>
      </n-layout-header>

      <n-layout-content
        class="home-content"
        :native-scrollbar="false"
        content-style="padding: 16px 20px 24px;"
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
  padding: 12px 20px 8px;
  background: var(--fa-bg-elevated);
  flex-shrink: 0;
}

.page-header {
  margin-top: 8px;
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
</style>
