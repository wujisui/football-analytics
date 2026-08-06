<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import FavoriteDatesPicker from '@/views/Favorites/components/FavoriteDatesPicker.vue'
import FavoriteFixtureCard from '@/views/Favorites/components/FavoriteFixtureCard.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import LeagueMenu from '@/layouts/components/LeagueMenu.vue'
import ShellBreadcrumb from '@/layouts/components/ShellBreadcrumb.vue'
import { useIsPhone } from '@/composables/useMediaQuery'
import {
  favoriteFixtureDays,
  useFavoriteFixtures,
} from '@/composables/useFavoriteFixtures'
import type { LeagueSummaryResponse } from '@/api/types'
import { parseApiDate, toScheduleDayKey } from '@/utils/format'
import { fixtureDetailRoute } from '@/utils/detailNav'
import { todayDate } from '@/utils/homeDateStrip'
import { leagueLabel } from '@/utils/leagueNames'

defineOptions({ name: 'Favorites' })

const FILTER_DATE_KEY = 'fa-favorites-filter-date'
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

function readSavedFilterDate(): string {
  try {
    const raw = localStorage.getItem(FILTER_DATE_KEY)
    if (raw && DATE_RE.test(raw)) return raw
  } catch {
    /* ignore */
  }
  return todayDate()
}

function writeSavedFilterDate(date: string) {
  try {
    localStorage.setItem(FILTER_DATE_KEY, date)
  } catch {
    /* ignore */
  }
}

const router = useRouter()
const isPhone = useIsPhone()
const { favorites, reloadFavorites } = useFavoriteFixtures()

const filterDate = ref<string>(readSavedFilterDate())
const selectedLeagueId = ref<number | null>(null)
const siderCollapsed = ref(false)
const refreshing = ref(false)
const favoritesShellRef = ref<HTMLElement | null>(null)

watch(filterDate, writeSavedFilterDate)

async function refreshList() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await reloadFavorites()
  } finally {
    refreshing.value = false
  }
}

const favoriteDays = computed(() => favoriteFixtureDays(favorites.value))

const dayFavorites = computed(() => {
  const day = filterDate.value
  return favorites.value
    .filter((item) => toScheduleDayKey(item.fixture_date) === day)
    .sort(
      (a, b) =>
        parseApiDate(a.fixture_date).getTime() -
        parseApiDate(b.fixture_date).getTime(),
    )
})

const favoriteCountByLeague = computed(() => {
  const counts = new Map<number, number>()
  for (const item of dayFavorites.value) {
    counts.set(item.league_id, (counts.get(item.league_id) || 0) + 1)
  }
  return counts
})

const favoriteLeagues = computed<LeagueSummaryResponse[]>(() => {
  const leagues = new Map<number, LeagueSummaryResponse>()
  for (const item of dayFavorites.value) {
    if (leagues.has(item.league_id)) continue
    leagues.set(item.league_id, {
      league_id: item.league_id,
      league_name: item.league_name,
      country: item.league_country ?? null,
      today_fixtures_count: 0,
      upcoming_fixtures_count: 0,
    })
  }
  return [...leagues.values()]
})

const filteredFavorites = computed(() => {
  const leagueId = selectedLeagueId.value
  if (leagueId == null) return dayFavorites.value
  return dayFavorites.value.filter((item) => item.league_id === leagueId)
})

const selectedLeagueLabel = computed(() => {
  if (selectedLeagueId.value == null) return '全部'
  const league = favoriteLeagues.value.find(
    (item) => item.league_id === selectedLeagueId.value,
  )
  return league ? leagueLabel(league.league_name) : '全部'
})

const dayCountLabel = computed(() => `${filteredFavorites.value.length} 场`)

watch(favoriteLeagues, (leagues) => {
  const selected = selectedLeagueId.value
  if (selected != null && !leagues.some((item) => item.league_id === selected)) {
    selectedLeagueId.value = null
  }
})

function goDetail(fixtureId: number) {
  void router.push(fixtureDetailRoute(fixtureId, { from: 'favorites' }))
}

onMounted(() => {
  void refreshList()
})
</script>

<template>
  <div class="fa-page-frame">
    <div class="fa-page-shell favorites-panel">
      <n-layout-sider
        v-if="!isPhone"
        v-model:collapsed="siderCollapsed"
        class="favorites-sider"
        collapse-mode="width"
        :collapsed-width="64"
        :width="232"
        :native-scrollbar="false"
        show-trigger="bar"
        content-style="height: 100%;"
      >
        <LeagueMenu
          :leagues="favoriteLeagues"
          :selected-league-id="selectedLeagueId"
          :count-by-league="favoriteCountByLeague"
          :total-count="dayFavorites.length"
          :loading="refreshing"
          :collapsed="siderCollapsed"
          @select="selectedLeagueId = $event"
        />
      </n-layout-sider>

      <section class="favorites-main">
        <div class="favorites-header fa-page-toolbar">
          <!-- 手机沿用比赛顶栏节奏，日期选择器占搜索槽位 -->
          <div v-if="isPhone" class="fa-toolbar-top">
            <span class="favorites-title">关注</span>
            <span class="fa-toolbar-day-stat">{{ dayCountLabel }}</span>
            <div class="fa-toolbar-end">
              <FavoriteDatesPicker
                v-model="filterDate"
                :marked-days="favoriteDays"
                legend="当天有关注（赛程日）"
              />
            </div>
          </div>

          <!-- PC 对齐比赛页：面包屑在上，列表统计与日期在下 -->
          <template v-else>
            <div class="fa-toolbar-top">
              <ShellBreadcrumb
                root-label="关注"
                :filter-label="selectedLeagueLabel"
                @select-root="selectedLeagueId = null"
              />
            </div>
            <div class="fa-toolbar-list-meta">
              <span class="fa-toolbar-day-stat">{{ dayCountLabel }}</span>
              <FavoriteDatesPicker
                v-model="filterDate"
                :marked-days="favoriteDays"
                legend="当天有关注（赛程日）"
              />
            </div>
          </template>
        </div>

        <n-spin :show="refreshing" class="favorites-body">
          <div ref="favoritesShellRef" class="favorites-list-shell">
            <n-scrollbar class="favorites-scroll" trigger="hover">
              <div class="fa-page-content-padding favorites-scroll-pad">
                <n-empty
                  v-if="!filteredFavorites.length"
                  :description="`${filterDate} 无关注场次`"
                  class="favorites-empty"
                />
                <div v-else class="favorites-card-stack">
                  <FavoriteFixtureCard
                    v-for="item in filteredFavorites"
                    :key="item.fixture_id"
                    :item="item"
                    @open-detail="goDetail"
                  />
                </div>
              </div>
            </n-scrollbar>
            <ListBackTop :shell="favoritesShellRef" :right="12" :bottom="12" />
          </div>
        </n-spin>
      </section>
    </div>
  </div>
</template>

<style scoped>
.favorites-panel {
  display: flex;
  overflow: hidden;
  background: var(--fa-bg);
}

.favorites-sider {
  position: relative;
  z-index: 3;
  flex-shrink: 0;
  box-shadow: var(--fa-sider-shadow);
}

.favorites-main {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
}

.favorites-header {
  flex-shrink: 0;
  width: 100%;
  box-sizing: border-box;
  box-shadow: var(--fa-header-shadow);
}

.favorites-title {
  flex-shrink: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--fa-text-strong);
}

.favorites-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.favorites-body :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.favorites-list-shell {
  position: relative;
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.favorites-scroll {
  flex: 1;
  min-height: 0;
}

.favorites-scroll-pad {
  padding-block: 8px 16px;
}

.favorites-empty {
  padding: 32px 12px;
}

.favorites-card-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
