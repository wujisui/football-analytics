<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import FavoriteDatesPicker from '@/views/Favorites/components/FavoriteDatesPicker.vue'
import FavoriteFixtureCard from '@/views/Favorites/components/FavoriteFixtureCard.vue'
import HomeDateStrip from '@/layouts/components/HomeDateStrip.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import {
  favoriteFixtureDays,
  useFavoriteFixtures,
} from '@/composables/useFavoriteFixtures'
import { useIsPhone } from '@/composables/useMediaQuery'
import { parseApiDate, toScheduleDayKey } from '@/utils/format'
import { fixtureDetailRoute } from '@/utils/detailNav'
import { todayDate } from '@/utils/homeDateStrip'

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

const filteredFavorites = computed(() => {
  const day = filterDate.value
  return favorites.value
    .filter((item) => toScheduleDayKey(item.fixture_date) === day)
    .sort(
      (a, b) =>
        parseApiDate(a.fixture_date).getTime() -
        parseApiDate(b.fixture_date).getTime(),
    )
})

function goDetail(fixtureId: number) {
  void router.push(fixtureDetailRoute(fixtureId, { from: 'favorites' }))
}

onMounted(() => {
  void refreshList()
})
</script>

<template>
  <div class="favorites-panel">
    <div class="favorites-header fa-page-toolbar">
      <HomeDateStrip v-if="isPhone" v-model="filterDate" />
      <div class="favorites-toolbar">
        <span class="favorites-title">关注</span>
        <FavoriteDatesPicker
          v-if="!isPhone"
          v-model="filterDate"
          :marked-days="favoriteDays"
          legend="当天有关注（赛程日）"
        />
        <n-text v-else depth="3">{{ filteredFavorites.length }} 场</n-text>
      </div>
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
  </div>
</template>

<style scoped>
.favorites-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--fa-bg);
}

.favorites-header {
  flex-shrink: 0;
  width: 100%;
  box-sizing: border-box;
}

.favorites-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.favorites-header :deep(.date-strip) {
  margin: 0 auto;
}

.favorites-title {
  flex-shrink: 0;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.2;
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
