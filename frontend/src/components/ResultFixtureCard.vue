<script setup lang="ts">
import { computed } from 'vue'

import type { FavoriteFixtureRecord } from '@/api/favorites'
import type { ResultFixture } from '@/api/fixtures'
import FavoriteButton from '@/components/FavoriteButton.vue'
import ResultPredictionSummary from '@/components/ResultPredictionSummary.vue'
import ScoreDetailLink from '@/components/ScoreDetailLink.vue'
import {
  formatDate,
  formatTime,
  leagueTagColor,
  resultStatusTagType,
  statusLabel,
} from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'
import {
  resultExtraScoreLine,
  resultScoreText,
} from '@/utils/resultsDisplay'

const props = withDefaults(defineProps<{
  fixture: ResultFixture | FavoriteFixtureRecord
  oddsClickable?: boolean
  showProbabilities?: boolean
}>(), {
  oddsClickable: false,
  showProbabilities: false,
})

const emit = defineEmits<{
  openDetail: [fixtureId: number]
  openOdds: []
}>()

const homeName = computed(() => props.fixture.home_team_name || '—')
const awayName = computed(() => props.fixture.away_team_name || '—')
const scoreText = computed(() => resultScoreText(props.fixture))
const extraScoreLine = computed(() => resultExtraScoreLine(props.fixture))
const statusShort = computed(() =>
  'status_short' in props.fixture ? props.fixture.status_short : undefined,
)
const resultFixturePayload = computed(() =>
  'home_team_id' in props.fixture ? props.fixture : undefined,
)
const hasProbabilityRow = computed(
  () =>
    props.showProbabilities
    && 'probabilities_available' in props.fixture
    && !!props.fixture.probabilities_available,
)

function openDetail() {
  emit('openDetail', props.fixture.fixture_id)
}
</script>

<template>
  <article
    class="result-fixture-card"
    :class="{ 'with-probabilities': hasProbabilityRow }"
  >
    <header class="card-head">
      <n-tag
        size="small"
        :bordered="false"
        :color="{
          color: `${leagueTagColor(fixture.league_id)}18`,
          textColor: leagueTagColor(fixture.league_id),
        }"
      >
        {{ leagueLabel(fixture.league_name) }}
      </n-tag>
      <span class="kickoff">
        {{ formatDate(fixture.fixture_date) }} {{ formatTime(fixture.fixture_date) }}
      </span>
      <n-tag
        size="small"
        :type="resultStatusTagType(fixture.status || '', statusShort)"
        :bordered="false"
      >
        {{ statusLabel(fixture.status || '', statusShort) }}
      </n-tag>
      <FavoriteButton
        :fixture-id="fixture.fixture_id"
        :result-fixture="resultFixturePayload"
        size="tiny"
      />
    </header>

    <div class="matchup">
      <span class="team home">{{ homeName }}</span>
      <ScoreDetailLink
        class="score"
        :label="scoreText"
        @click="openDetail"
      />
      <span class="team away">{{ awayName }}</span>
    </div>
    <p v-if="extraScoreLine" class="score-extra">{{ extraScoreLine }}</p>

    <ResultPredictionSummary
      :fixture="fixture"
      :odds-clickable="oddsClickable"
      :show-probabilities="showProbabilities"
      @open-odds="emit('openOdds')"
    />
  </article>
</template>

<style scoped>
.result-fixture-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  background: var(--fa-bg-soft);
}

.result-fixture-card.with-probabilities {
  gap: 6px;
  justify-content: space-between;
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

.score {
  flex-shrink: 0;
  font-size: 14px;
}

.score-extra {
  margin: -4px 0 0;
  text-align: center;
  font-size: 11px;
  color: var(--fa-text-secondary);
}
</style>
