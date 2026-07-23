<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import FavoriteDatesPicker from '@/components/FavoriteDatesPicker.vue'
import FavoriteFixtureCard from '@/components/FavoriteFixtureCard.vue'
import { favoriteFixtureDays, useFavoriteFixtures } from '@/composables/useFavoriteFixtures'
import { useFavoritesDrawer } from '@/composables/useFavoritesDrawer'
import { useIsPhone } from '@/composables/useMediaQuery'
import { parseApiDate, toScheduleDayKey } from '@/utils/format'
import { fixtureDetailRoute } from '@/utils/detailNav'
import { todayDate } from '@/utils/homeDateStrip'

const router = useRouter()
const isPhone = useIsPhone()
const { show, close } = useFavoritesDrawer()
const { favorites, reloadFavorites } = useFavoriteFixtures()

const filterDate = ref<string | null>(todayDate())
const refreshing = ref(false)

watch(show, (open) => {
  if (!open) return
  filterDate.value = todayDate()
  void refreshDrawer()
})

async function refreshDrawer() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await reloadFavorites()
  } finally {
    refreshing.value = false
  }
}

const favoriteDays = computed(() => favoriteFixtureDays(favorites.value))

const todayFavoriteCount = computed(() => {
  const today = todayDate()
  return favorites.value.filter(
    (item) => toScheduleDayKey(item.fixture_date) === today,
  ).length
})

const filteredFavorites = computed(() => {
  let list = [...favorites.value]
  if (filterDate.value) {
    list = list.filter(
      (item) => toScheduleDayKey(item.fixture_date) === filterDate.value,
    )
  }
  return list.sort(
    (a, b) =>
      parseApiDate(a.fixture_date).getTime() -
      parseApiDate(b.fixture_date).getTime(),
  )
})

function goDetail(fixtureId: number) {
  close()
  void router.push(fixtureDetailRoute(fixtureId, { from: 'favorites' }))
}
</script>

<template>
  <n-drawer
    v-model:show="show"
    :width="isPhone ? '92%' : 'min(820px, 92vw)'"
    placement="left"
    to="body"
    display-directive="show"
  >
    <n-drawer-content closable :native-scrollbar="false" class="favorites-drawer-content">
      <template #header>
        <div class="drawer-header">
          <div class="drawer-head">
            <span class="drawer-title">收藏</span>
            <n-text depth="3" class="drawer-count">
              共 {{ favorites.length }} 场
            </n-text>
            <n-text depth="3" class="drawer-count drawer-count-sep">
              今日 {{ todayFavoriteCount }} 场
            </n-text>
          </div>
          <div class="drawer-toolbar">
            <FavoriteDatesPicker
              v-model="filterDate"
              :favorite-days="favoriteDays"
            />
          </div>
        </div>
      </template>

      <n-spin :show="refreshing" class="drawer-body">
        <n-scrollbar class="drawer-scroll" trigger="hover">
          <n-empty
            v-if="!filteredFavorites.length"
            :description="
              filterDate
                ? `${filterDate} 无收藏场次`
                : '暂无收藏，可在列表或详情页点击星标'
            "
            class="drawer-empty"
          />
          <div v-else class="favorites-card-stack">
            <FavoriteFixtureCard
              v-for="item in filteredFavorites"
              :key="item.fixture_id"
              :item="item"
              @open-detail="goDetail"
            />
          </div>
        </n-scrollbar>
      </n-spin>
    </n-drawer-content>
  </n-drawer>
</template>

<style scoped>
.favorites-drawer-content :deep(.n-drawer-body) {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding-top: 0;
  overflow: hidden;
}

.favorites-drawer-content :deep(.n-drawer-body-content-wrapper) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.drawer-header {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.drawer-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.drawer-title {
  font-size: 16px;
  font-weight: 700;
}

.drawer-count {
  font-size: 12px;
}

.drawer-count-sep::before {
  content: '·';
  margin: 0 6px 0 2px;
  opacity: 0.55;
}

.drawer-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.drawer-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.drawer-body :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.drawer-scroll {
  flex: 1;
  min-height: 0;
  padding: 0 2px 8px;
}

.drawer-empty {
  padding: 32px 12px;
}

.favorites-card-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
