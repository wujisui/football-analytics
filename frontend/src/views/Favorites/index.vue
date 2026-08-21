<script setup lang="ts">
import { computed, onActivated, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import FavoriteDatesPicker from '@/views/Favorites/components/FavoriteDatesPicker.vue'
import FavoriteFixtureCard from '@/views/Favorites/components/FavoriteFixtureCard.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import LeagueMenu from '@/layouts/components/LeagueMenu.vue'
import ShellBreadcrumb from '@/layouts/components/ShellBreadcrumb.vue'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useMarkedFixture } from '@/composables/useMarkedFixture'
import {
  favoriteFixtureDays,
  nearestFavoriteDay,
  useFavoriteFixtures,
} from '@/composables/useFavoriteFixtures'
import type { LeagueSummaryResponse } from '@/api/types'
import { toScheduleDayKey } from '@/utils/format'
import { fixtureDetailRoute } from '@/utils/detailNav'
import { sortFixturesFavoritesFirst } from '@/utils/fixtureSort'
import { scheduleTodayDate, todayDate } from '@/utils/homeDateStrip'
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
const { favorites, favoriteIds, dailyPickIds, ensureLoaded, refresh } =
  useFavoriteFixtures()

const filterDate = ref<string>(readSavedFilterDate())
const selectedLeagueId = ref<number | null>(null)
const siderCollapsed = ref(false)
const favoritesShellRef = ref<HTMLElement | null>(null)
const { markedFixtureId, toggleMarked, clearMarked, retainIfPresent } =
  useMarkedFixture()

watch(filterDate, (day) => {
  writeSavedFilterDate(day)
  clearMarked()
})

watch(selectedLeagueId, () => clearMarked())

const favoriteDays = computed(() => favoriteFixtureDays(favorites.value))

const dayFavorites = computed(() => {
  const day = filterDate.value
  const list = favorites.value.filter(
    (item) => toScheduleDayKey(item.fixture_date) === day,
  )
  return sortFixturesFavoritesFirst(list, favoriteIds.value, dailyPickIds.value)
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

watch(
  () => filteredFavorites.value.map((item) => item.fixture_id),
  (ids) => retainIfPresent(ids),
)

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

/** Avoid empty "today" while auto picks sit on later match days. */
function snapFilterToAvailableDay() {
  if (dayFavorites.value.length > 0) return
  const next = nearestFavoriteDay(favoriteDays.value, scheduleTodayDate())
  if (next && next !== filterDate.value) {
    filterDate.value = next
  }
}

async function reloadFavorites(force: boolean) {
  await (force ? refresh() : ensureLoaded())
  snapFilterToAvailableDay()
}

/**
 * keep-alive 下首次挂载也会触发 onActivated，所以不另挂 onMounted。
 * 首次激活复用应用启动时那次加载（本页 chunk 通常比接口慢，强制刷新会多打一次）；
 * 之后每次回到本页才真正重读，收藏可能在别处被改过。
 */
let visited = false
onActivated(() => {
  void reloadFavorites(visited)
  visited = true
})
</script>

<template>
  <div class="fa-page-frame">
    <n-layout
      :has-sider="!isPhone"
      class="favorites-panel fa-page-shell"
      content-style="height: 100%;"
    >
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
          :collapsed="siderCollapsed"
          @select="selectedLeagueId = $event"
        />
      </n-layout-sider>

      <section class="favorites-main fa-page-main">
        <!-- 标题行：手机居中标题（对齐我的方案），PC 面包屑 + 统计/日期同一块顶栏 -->
        <div class="favorites-header fa-page-toolbar">
          <div
            class="fa-toolbar-top"
            :class="{ 'fa-toolbar-centered': isPhone }"
          >
            <span v-if="isPhone" class="fa-toolbar-title">关注</span>
            <ShellBreadcrumb
              v-else
              root-label="关注"
              :filter-label="selectedLeagueLabel"
              @select-root="selectedLeagueId = null"
            />
          </div>
          <div v-if="!isPhone" class="fa-toolbar-list-meta">
            <span class="fa-toolbar-day-stat">{{ dayCountLabel }}</span>
            <FavoriteDatesPicker
              v-model="filterDate"
              :marked-days="favoriteDays"
              legend="当天有关注（赛程日）"
            />
          </div>
        </div>

        <div class="favorites-body">
          <!-- 手机：统计/日期做成卡片头，与列表合成整块；PC 这两项在顶栏第二行 -->
          <n-card
            class="favorites-card"
            :class="{ 'favorites-card--mobile': isPhone }"
            :bordered="false"
            content-style="padding: 0; flex: 1; min-height: 0; display: flex; flex-direction: column;"
          >
            <template v-if="isPhone" #header>
              <span class="favorites-card-title">{{ dayCountLabel }}</span>
            </template>
            <template v-if="isPhone" #header-extra>
              <FavoriteDatesPicker
                v-model="filterDate"
                :marked-days="favoriteDays"
                legend="当天有关注（赛程日）"
              />
            </template>
            <div ref="favoritesShellRef" class="favorites-list-shell">
              <n-scrollbar class="favorites-scroll" trigger="hover">
                <div class="favorites-scroll-pad">
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
                      selectable
                      :selected="markedFixtureId === item.fixture_id"
                      @open-detail="goDetail"
                      @toggle-select="toggleMarked"
                    />
                  </div>
                </div>
              </n-scrollbar>
              <ListBackTop :shell="favoritesShellRef" :right="12" :bottom="12" />
            </div>
          </n-card>
        </div>
      </section>
    </n-layout>
  </div>
</template>

<style scoped>
.favorites-panel {
  height: 100%;
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
  flex-direction: column;
}

.favorites-header {
  position: relative;
  z-index: 2;
  flex-shrink: 0;
  width: 100%;
  box-sizing: border-box;
  box-shadow: var(--fa-header-shadow);
}

.favorites-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  /* 手机卡片的左右留白走父级 padding：n-card 自带 width:100%，
     用 margin 会让盒宽仍等于父宽而向右溢出被裁掉 */
  padding: 0 12px;
  box-sizing: border-box;
}

/* PC：卡片透明无边框，等同裸列表（统计/日期在顶栏第二行，保持原样） */
.favorites-card {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: transparent;
}

/* 手机：统计/日期 + 列表合成一个抬升卡片，与顶部标题分层 */
.favorites-card--mobile {
  margin: 12px 0;
  background: var(--fa-bg-elevated);
  border-radius: 12px;
  overflow: hidden;
}

.favorites-card--mobile :deep(.n-card-header) {
  flex-shrink: 0;
  padding: 12px 14px;
  border-bottom: 1px solid var(--fa-border);
}

.favorites-card-title {
  font-size: 13px;
  color: var(--fa-text-secondary);
  white-space: nowrap;
}

/* PC 保持原样：裸列表，左右留白由 scroll-pad 给 */
@media (min-width: 768px) {
  .favorites-body {
    padding: 0;
  }
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

/* 与我的方案面板同一档左右留白 */
.favorites-scroll-pad {
  padding: 8px 12px 16px;
  box-sizing: border-box;
}

/* 手机：屏幕留白已由外层卡片承担，赛事卡铺满卡片内宽，
   否则再缩一档会挤到推荐 tag 换行 */
.favorites-card--mobile .favorites-scroll-pad {
  padding-inline: 0;
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
