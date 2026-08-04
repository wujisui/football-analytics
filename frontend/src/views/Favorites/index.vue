<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import FavoriteDatesPicker from '@/views/Favorites/components/FavoriteDatesPicker.vue'
import FavoriteFixtureCard from '@/views/Favorites/components/FavoriteFixtureCard.vue'
import {
  favoriteFixtureDays,
  useFavoriteFixtures,
  type FavoriteFixtureRecord,
} from '@/composables/useFavoriteFixtures'
import { formatScheduleDay, parseApiDate, toScheduleDayKey } from '@/utils/format'
import { groupFixturesByScheduleDay } from '@/utils/fixtureDayGroups'
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

type FavoriteBucket = {
  key: string
  title: string
  items: FavoriteFixtureRecord[]
}

const router = useRouter()
const { favorites, reloadFavorites } = useFavoriteFixtures()

const filterDate = ref<string | null>(readSavedFilterDate())
const refreshing = ref(false)

watch(filterDate, (date) => {
  // Clearable X replaces「今天」: empty → jump back to today.
  if (date == null) {
    filterDate.value = todayDate()
    return
  }
  writeSavedFilterDate(date)
})

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
  let list = [...favorites.value]
  if (day) {
    list = list.filter((item) => toScheduleDayKey(item.fixture_date) === day)
  }
  return list.sort(
    (a, b) =>
      parseApiDate(a.fixture_date).getTime() -
      parseApiDate(b.fixture_date).getTime(),
  )
})

/** Newest schedule day first; title is the calendar date only. */
const favoriteBuckets = computed((): FavoriteBucket[] =>
  groupFixturesByScheduleDay(filteredFavorites.value)
    .reverse()
    .map((group) => ({
      key: group.key,
      title: formatScheduleDay(group.key),
      items: group.fixtures,
    })),
)

const defaultExpandedName = computed(
  () => favoriteBuckets.value[0]?.key ?? null,
)

function goDetail(fixtureId: number) {
  void router.push(fixtureDetailRoute(fixtureId, { from: 'favorites' }))
}

onMounted(() => {
  void refreshList()
})
</script>

<template>
  <div class="fa-page-frame">
    <div class="fa-page-shell favorites-shell">
      <div class="favorites-header fa-page-toolbar">
        <div class="favorites-toolbar">
          <span class="favorites-title">收藏</span>
          <FavoriteDatesPicker
            v-model="filterDate"
            :favorite-days="favoriteDays"
          />
        </div>
      </div>

      <n-spin :show="refreshing" class="favorites-body">
        <n-scrollbar class="favorites-scroll" trigger="hover">
          <div class="fa-page-content-padding favorites-scroll-pad">
            <n-empty
              v-if="!favoriteBuckets.length"
              :description="
                filterDate
                  ? `${filterDate} 无收藏场次`
                  : '暂无收藏，可在列表或详情页点击星标'
              "
              class="favorites-empty"
            />
            <n-collapse
              v-else
              :key="`${filterDate ?? 'all'}-${favoriteBuckets.map((b) => b.key).join('-')}`"
              class="fa-day-collapse"
              accordion
              display-directive="if"
              :default-expanded-names="defaultExpandedName"
              arrow-placement="right"
            >
              <n-collapse-item
                v-for="bucket in favoriteBuckets"
                :key="bucket.key"
                :name="bucket.key"
              >
                <template #header>
                  <div class="fa-day-collapse-title">
                    <n-text strong class="fa-day-collapse-title__label">{{ bucket.title }}</n-text>
                    <n-text depth="3" class="fa-day-collapse-title__count">
                      {{ bucket.items.length }} 场
                    </n-text>
                  </div>
                </template>
                <div class="favorites-card-stack">
                  <FavoriteFixtureCard
                    v-for="item in bucket.items"
                    :key="item.fixture_id"
                    :item="item"
                    @open-detail="goDetail"
                  />
                </div>
              </n-collapse-item>
            </n-collapse>
          </div>
        </n-scrollbar>
      </n-spin>
    </div>
  </div>
</template>

<style scoped>
.favorites-shell {
  display: flex;
  flex-direction: column;
  background: var(--fa-bg);
}

.favorites-header {
  border-bottom: 1px solid var(--fa-border);
}

@media (max-width: 767px) {
  .favorites-header {
    border-bottom: none;
  }
}

.favorites-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
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
