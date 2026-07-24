<script setup lang="ts">
import { computed, ref } from 'vue'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FavoriteButton from '@/components/FavoriteButton.vue'
import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import ResultFixtureCard from '@/components/ResultFixtureCard.vue'
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
const showOddsPopover = ref(false)

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

function openDetail() {
  emit('openDetail', props.item.fixture_id)
}

</script>

<template>
  <n-popover
    v-if="isFinished && isPhone"
    v-model:show="showOddsPopover"
    trigger="manual"
    placement="bottom"
    :show-arrow="false"
    to="body"
    display-directive="show"
    :style="{ width: 'min(360px, calc(100vw - 24px))' }"
  >
    <template #trigger>
      <ResultFixtureCard
        :fixture="item"
        odds-clickable
        @open-detail="openDetail"
        @open-odds="showOddsPopover = true"
      />
    </template>
    <div class="favorite-odds-popover">
      <p class="odds-popover-title">
        {{ homeName }} vs {{ awayName }} · 赛前盘口
      </p>
      <PreMatchOddsTable
        :odds="item.odds_snippet"
        :home-name="homeName"
        :away-name="awayName"
        link-middle-to-detail
        :fixture-id="item.fixture_id"
        from="favorites"
      />
    </div>
  </n-popover>

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
        @open-detail="openDetail"
      />
    </div>
  </article>

  <article v-else class="favorite-fixture-card">
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

      <!-- Phone: keep card visible; odds open beside the trigger -->
      <n-popover
        v-if="isPhone"
        v-model:show="showOddsPopover"
        trigger="click"
        placement="bottom"
        :show-arrow="false"
        to="body"
        display-directive="show"
        :style="{ width: 'min(360px, calc(100vw - 24px))' }"
      >
        <template #trigger>
          <div
            class="odds-popover-trigger"
            :class="{ open: showOddsPopover }"
            role="button"
            tabindex="0"
            aria-label="查看赛前盘口"
          >
            <AlgorithmPredictionCard
              :snapshot="predictionSnapshot"
              :fixture-id="item.fixture_id"
              :show-matchup-title="false"
              from="favorites"
              class="predict-slot"
            />
          </div>
        </template>
        <div class="favorite-odds-popover">
          <p class="odds-popover-title">
            {{ homeName }} vs {{ awayName }} · 赛前盘口
          </p>
          <PreMatchOddsTable
            :odds="item.odds_snippet"
            :home-name="homeName"
            :away-name="awayName"
            link-middle-to-detail
            :fixture-id="item.fixture_id"
            from="favorites"
          />
        </div>
      </n-popover>

      <template v-else>
        <AlgorithmPredictionCard
          :snapshot="predictionSnapshot"
          :fixture-id="item.fixture_id"
          :show-matchup-title="false"
          from="favorites"
          class="predict-slot"
        />
      </template>
    </div>
    <n-text v-if="!hasPredict" depth="3" class="no-predict">
      暂无预测快照
    </n-text>
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
  min-width: 0;
  max-width: 100%;
}

.summary-grid.phone {
  grid-template-columns: minmax(0, 1fr);
}

.predict-slot :deep(.predict-card.zone) {
  height: 100%;
}

.odds-popover-trigger {
  min-width: 0;
  max-width: 100%;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s var(--n-bezier, ease);
}

.odds-popover-trigger:hover,
.odds-popover-trigger:focus-visible,
.odds-popover-trigger.open {
  outline: none;
  background: var(--fa-bg-soft);
}

.no-predict {
  font-size: 11px;
}
</style>

<style>
.favorite-odds-popover {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 100%;
}

.favorite-odds-popover .odds-popover-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--fa-text-strong);
  line-height: 1.4;
}
</style>
