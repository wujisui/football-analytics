<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import FavoriteButton from '@/components/FavoriteButton.vue'
import { useFavoriteFixtures } from '@/composables/useFavoriteFixtures'
import { useFavoritesDrawer } from '@/composables/useFavoritesDrawer'
import { useIsPhone } from '@/composables/useMediaQuery'
import { formatDateTime, leagueTagColor, statusLabel, statusTagType, toPercent } from '@/utils/format'
import { fixtureDetailRoute } from '@/utils/detailNav'
import { leagueLabel } from '@/utils/leagueNames'
import { todayDate } from '@/utils/homeDateStrip'

const router = useRouter()
const isPhone = useIsPhone()
const { show, close } = useFavoritesDrawer()
const { favorites, remove, favoriteHasPredictSnapshot, refreshFavoritePredictions } =
  useFavoriteFixtures()

const filterDate = ref<string | null>(todayDate())
const refreshing = ref(false)

watch(show, (open) => {
  if (!open) return
  filterDate.value = todayDate()
  void refreshDrawerPredictions()
})

async function refreshDrawerPredictions() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await refreshFavoritePredictions()
  } finally {
    refreshing.value = false
  }
}

function fixtureDay(iso: string): string {
  return iso.slice(0, 10)
}

const filteredFavorites = computed(() => {
  let list = [...favorites.value]
  if (filterDate.value) {
    list = list.filter((item) => fixtureDay(item.fixture_date) === filterDate.value)
  }
  return list.sort((a, b) => {
    const byDate = b.fixture_date.localeCompare(a.fixture_date)
    if (byDate !== 0) return byDate
    return b.saved_at.localeCompare(a.saved_at)
  })
})

function scoreText(item: (typeof favorites.value)[number]): string | null {
  const h = item.home_goals
  const a = item.away_goals
  if (h == null || a == null) return null
  return `${h}:${a}`
}

function goDetail(fixtureId: number) {
  close()
  void router.push(fixtureDetailRoute(fixtureId, { from: 'favorites' }))
}

function clearAll() {
  for (const item of favorites.value) {
    remove(item.fixture_id)
  }
}

function isPendingRec(text: string | undefined): boolean {
  return !text || text === '待分析'
}

function isPendingHandicap(text: string | undefined): boolean {
  return !text || text.includes('缺少盘口') || text.includes('待分析')
}
</script>

<template>
  <n-drawer
    v-model:show="show"
    :width="isPhone ? '88%' : 420"
    placement="left"
    to="body"
    display-directive="show"
  >
    <n-drawer-content closable :native-scrollbar="false">
      <template #header>
        <div class="drawer-head">
          <span class="drawer-title">收藏</span>
          <n-text depth="3" style="font-size: 12px;">
            {{ favorites.length }} 场
          </n-text>
        </div>
      </template>

      <div class="drawer-toolbar">
        <n-date-picker
          v-model:formatted-value="filterDate"
          value-format="yyyy-MM-dd"
          type="date"
          size="small"
          clearable
          placeholder="按开赛日筛选"
          style="flex: 1; min-width: 0;"
        />
        <n-button
          v-if="favorites.length"
          size="small"
          quaternary
          @click="clearAll"
        >
          清空
        </n-button>
      </div>

      <n-spin :show="refreshing">
      <n-scrollbar class="drawer-scroll" trigger="hover">
        <n-empty
          v-if="!filteredFavorites.length"
          :description="
            filterDate
              ? `${filterDate} 无收藏场次`
              : '暂无收藏，可在列表或详情页点击星标'
          "
          style="padding: 32px 12px;"
        />
        <n-list v-else bordered size="small">
          <n-list-item v-for="item in filteredFavorites" :key="item.fixture_id">
            <n-thing>
              <template #header>
                <n-space :size="6" align="center" wrap>
                  <n-tag
                    size="small"
                    :bordered="false"
                    :color="{
                      color: `${leagueTagColor(item.league_id)}18`,
                      textColor: leagueTagColor(item.league_id),
                    }"
                  >
                    {{ leagueLabel(item.league_name) }}
                  </n-tag>
                  <span class="kickoff">{{ formatDateTime(item.fixture_date) }}</span>
                </n-space>
              </template>
              <template #header-extra>
                <n-space :size="4" align="center">
                  <n-tag
                    v-if="item.status"
                    size="small"
                    :type="statusTagType(item.status)"
                    :bordered="false"
                  >
                    {{ statusLabel(item.status) }}
                  </n-tag>
                  <FavoriteButton :fixture-id="item.fixture_id" />
                </n-space>
              </template>
              <div class="match-row">
                <span class="team">{{ item.home_team_name }}</span>
                <n-button
                  text
                  type="primary"
                  class="score-btn"
                  @click="goDetail(item.fixture_id)"
                >
                  {{ scoreText(item) ?? 'VS' }}
                </n-button>
                <span class="team away">{{ item.away_team_name }}</span>
              </div>
              <div v-if="favoriteHasPredictSnapshot(item)" class="predict-block">
                <div class="rec-row">
                  <span class="rec-label">推荐</span>
                  <n-tag
                    size="tiny"
                    :type="isPendingRec(item.recommendation) ? 'default' : 'primary'"
                  >
                    {{ item.recommendation || '—' }}
                  </n-tag>
                  <n-tag
                    v-if="item.handicap_lean"
                    size="tiny"
                    :type="isPendingHandicap(item.handicap_lean) ? 'default' : 'warning'"
                  >
                    {{ item.handicap_lean }}
                  </n-tag>
                </div>
                <div
                  v-if="item.probabilities_available"
                  class="prob-row"
                >
                  <span>主 {{ toPercent(item.home_win_prob ?? 0) }}</span>
                  <span>平 {{ toPercent(item.draw_prob ?? 0) }}</span>
                  <span>客 {{ toPercent(item.away_win_prob ?? 0) }}</span>
                </div>
                <n-text depth="3" class="lean-line">
                  {{ item.score_hint || '—' }}
                  · {{ item.goal_lean || '—' }}
                  · {{ item.both_score_lean || '—' }}
                </n-text>
              </div>
              <n-text v-else depth="3" class="no-predict">暂无预测快照</n-text>
            </n-thing>
          </n-list-item>
        </n-list>
      </n-scrollbar>
      </n-spin>
    </n-drawer-content>
  </n-drawer>
</template>

<style scoped>
.drawer-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.drawer-title {
  font-size: 16px;
  font-weight: 700;
}

.drawer-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.drawer-scroll {
  flex: 1;
  min-height: 0;
  max-height: calc(100vh - 160px);
}

.kickoff {
  font-size: 12px;
  color: var(--fa-text-secondary);
}

.match-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 8px;
  align-items: center;
  margin-top: 4px;
  font-weight: 600;
}

.team {
  font-size: 13px;
  text-align: right;
}

.team.away {
  text-align: left;
}

.score-btn {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}

.predict-block {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rec-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.rec-label {
  font-size: 11px;
  color: var(--fa-text-secondary);
}

.prob-row {
  display: flex;
  gap: 10px;
  font-size: 11px;
  color: var(--fa-text-secondary);
  font-variant-numeric: tabular-nums;
}

.lean-line {
  font-size: 11px;
  line-height: 1.45;
}

.no-predict {
  display: block;
  margin-top: 6px;
  font-size: 11px;
}
</style>
