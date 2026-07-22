<script setup lang="ts">
import { computed } from 'vue'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FavoriteButton from '@/components/FavoriteButton.vue'
import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import {
  favoriteHasPredictSnapshot,
  snapshotFromFavorite,
  type FavoriteFixtureRecord,
} from '@/composables/useFavoriteFixtures'
import {
  formatDate,
  formatTime,
  leagueTagColor,
  statusLabel,
  statusTagType,
} from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'

const props = defineProps<{
  item: FavoriteFixtureRecord
}>()

const emit = defineEmits<{
  openDetail: [fixtureId: number]
}>()

const homeName = computed(() => props.item.home_team_name || '—')
const awayName = computed(() => props.item.away_team_name || '—')

const scoreText = computed(() => {
  const h = props.item.home_goals
  const a = props.item.away_goals
  if (h == null || a == null) return null
  return `${h}:${a}`
})

const hasPredict = computed(() => favoriteHasPredictSnapshot(props.item))
const predictionSnapshot = computed(() => snapshotFromFavorite(props.item))

function openDetail() {
  emit('openDetail', props.item.fixture_id)
}
</script>

<template>
  <article class="favorite-fixture-card">
    <header class="card-head">
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
      <span class="kickoff">
        {{ formatDate(item.fixture_date) }} {{ formatTime(item.fixture_date) }}
      </span>
      <n-tag
        v-if="item.status"
        size="small"
        :type="statusTagType(item.status)"
        :bordered="false"
      >
        {{ statusLabel(item.status) }}
      </n-tag>
      <FavoriteButton :fixture-id="item.fixture_id" size="tiny" />
    </header>

    <div class="matchup">
      <span class="team home">{{ homeName }}</span>
      <button
        type="button"
        class="score-btn"
        :aria-label="`查看 ${homeName} 对 ${awayName} 详情`"
        @click="openDetail"
      >
        {{ scoreText ?? 'VS' }}
      </button>
      <span class="team away">{{ awayName }}</span>
    </div>

    <div v-if="hasPredict" class="summary-grid">
      <PreMatchOddsTable
        :odds="item.odds_snippet"
        :home-name="homeName"
        :away-name="awayName"
        link-middle-to-detail
        :fixture-id="item.fixture_id"
        from="favorites"
      />
      <AlgorithmPredictionCard
        :snapshot="predictionSnapshot"
        :fixture-id="item.fixture_id"
        :show-matchup-title="false"
        from="favorites"
        class="predict-slot"
      />
    </div>
    <n-text v-else depth="3" class="no-predict">暂无预测快照</n-text>
  </article>
</template>

<style scoped>
.favorite-fixture-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  background: var(--fa-bg-elevated);
}

.card-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.kickoff {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: var(--fa-text-secondary);
}

.matchup {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-weight: 600;
}

.team {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.team.home {
  text-align: right;
}

.team.away {
  text-align: left;
}

.score-btn {
  appearance: none;
  margin: 0;
  padding: 0;
  border: none;
  background: none;
  color: var(--fa-text-strong);
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  cursor: pointer;
  flex-shrink: 0;
}

.score-btn:hover {
  color: var(--fa-highlight-text);
}

.score-btn:focus-visible {
  outline: 2px solid var(--fa-highlight-border);
  outline-offset: 2px;
  border-radius: 2px;
}

.summary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  align-items: stretch;
}

.predict-slot :deep(.predict-card.zone) {
  height: 100%;
}

.no-predict {
  font-size: 11px;
}
</style>
