<script setup lang="ts">
import { computed, ref } from 'vue'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FavoriteButton from '@/components/FavoriteButton.vue'
import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import ResultFixtureCard from '@/components/ResultFixtureCard.vue'
import ScoreDetailLink from '@/components/ScoreDetailLink.vue'
import {
  favoriteHasPredictSnapshot,
  snapshotFromFavorite,
  type FavoriteFixtureRecord,
} from '@/composables/useFavoriteFixtures'
import { useIsPhone } from '@/composables/useMediaQuery'
import {
  formatDate,
  formatTime,
  leagueTagColor,
  statusLabel,
  statusTagType,
} from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'
import { resultScoreText } from '@/utils/resultsDisplay'

const props = defineProps<{
  item: FavoriteFixtureRecord
}>()

const emit = defineEmits<{
  openDetail: [fixtureId: number]
}>()

const isPhone = useIsPhone()
const showOddsModal = ref(false)

const homeName = computed(() => props.item.home_team_name || '—')
const awayName = computed(() => props.item.away_team_name || '—')

const scoreText = computed(() => {
  if (props.item.home_goals == null || props.item.away_goals == null) return null
  return resultScoreText(props.item)
})

const hasPredict = computed(() => favoriteHasPredictSnapshot(props.item))
const predictionSnapshot = computed(() => snapshotFromFavorite(props.item))

/** Any settled fixture uses the same card as the results list. */
const isFinished = computed(() => {
  const status = (props.item.status || '').toLowerCase()
  if (status === 'finished') return true
  return props.item.home_goals != null && props.item.away_goals != null
})

const showPredictBlock = computed(() => hasPredict.value)
const oddsModalTitle = computed(
  () => `${homeName.value} vs ${awayName.value} · 赛前盘口`,
)

function openDetail() {
  emit('openDetail', props.item.fixture_id)
}

function openOddsModal() {
  showOddsModal.value = true
}
</script>

<template>
  <ResultFixtureCard
    v-if="isFinished && isPhone"
    :fixture="item"
    odds-clickable
    @open-detail="openDetail"
    @open-odds="openOddsModal"
  />

  <article v-else-if="isFinished" class="favorite-fixture-card">
    <div class="finished-favorite-grid">
      <PreMatchOddsTable
        :odds="item.odds_snippet"
        :home-name="homeName"
        :away-name="awayName"
        link-middle-to-detail
        :fixture-id="item.fixture_id"
        from="favorites"
      />
      <ResultFixtureCard
        :fixture="item"
        show-probabilities
        @open-detail="openDetail"
      />
    </div>
  </article>

  <article v-else class="favorite-fixture-card">
    <header class="card-head">
      <span class="league-tag-tip">
        <n-tooltip :trigger="isPhone ? 'click' : 'hover'" placement="top">
          <template #trigger>
            <n-tag
              class="league-tag"
              size="small"
              :bordered="false"
              :color="{
                color: `${leagueTagColor(item.league_id)}18`,
                textColor: leagueTagColor(item.league_id),
              }"
            >
              {{ leagueLabel(item.league_name) }}
            </n-tag>
          </template>
          {{ leagueLabel(item.league_name) }}
        </n-tooltip>
      </span>
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
      <ScoreDetailLink
        class="score-btn"
        :label="scoreText ?? 'VS'"
        @click="openDetail"
      />
      <span class="team away">{{ awayName }}</span>
    </div>

    <div
      v-if="showPredictBlock"
      class="summary-grid"
      :class="{ phone: isPhone }"
    >
      <PreMatchOddsTable
        v-if="!isPhone"
        :odds="item.odds_snippet"
        :home-name="homeName"
        :away-name="awayName"
        link-middle-to-detail
        :fixture-id="item.fixture_id"
        from="favorites"
      />

      <div
        v-if="isPhone"
        class="odds-modal-trigger"
        role="button"
        tabindex="0"
        aria-label="查看赛前盘口"
        @click="openOddsModal"
        @keydown.enter.prevent="openOddsModal"
      >
        <AlgorithmPredictionCard
          :snapshot="predictionSnapshot"
          :fixture-id="item.fixture_id"
          :show-matchup-title="false"
          from="favorites"
          class="predict-slot"
        />
      </div>
      <AlgorithmPredictionCard
        v-else
        :snapshot="predictionSnapshot"
        :fixture-id="item.fixture_id"
        :show-matchup-title="false"
        from="favorites"
        class="predict-slot"
      />
    </div>
    <n-text v-if="!hasPredict" depth="3" class="no-predict">
      暂无预测快照
    </n-text>
  </article>

  <n-modal
    v-if="isPhone"
    v-model:show="showOddsModal"
    preset="card"
    :title="oddsModalTitle"
    :style="{ width: 'min(360px, calc(100vw - 24px))' }"
    :segmented="{ content: true, footer: false }"
  >
    <PreMatchOddsTable
      :odds="item.odds_snippet"
      :home-name="homeName"
      :away-name="awayName"
      link-middle-to-detail
      :fixture-id="item.fixture_id"
      from="favorites"
    />
  </n-modal>
</template>

<style scoped>
.favorite-fixture-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  background: var(--fa-bg-elevated);
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.finished-favorite-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  align-items: stretch;
  min-width: 0;
  max-width: 100%;
}

.finished-favorite-grid > :deep(*) {
  min-width: 0;
}

.finished-favorite-grid :deep(.result-fixture-card) {
  height: 100%;
  box-sizing: border-box;
}

.card-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.league-tag-tip {
  flex: 0 1 42%;
  min-width: 0;
  max-width: 42%;
}

.league-tag-tip :deep(.n-tooltip) {
  display: block;
  max-width: 100%;
}

.league-tag {
  max-width: 100%;
}

:deep(.league-tag .n-tag__content) {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  flex-shrink: 0;
  font-size: 14px;
}

.summary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  align-items: stretch;
  min-width: 0;
  max-width: 100%;
}

.summary-grid.phone {
  grid-template-columns: minmax(0, 1fr);
}

.predict-slot :deep(.predict-card.zone) {
  height: 100%;
}

.odds-modal-trigger {
  min-width: 0;
  max-width: 100%;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s var(--n-bezier, ease);
}

.odds-modal-trigger:hover,
.odds-modal-trigger:focus-visible {
  outline: none;
  background: var(--fa-bg-soft);
}

.no-predict {
  font-size: 11px;
}
</style>
