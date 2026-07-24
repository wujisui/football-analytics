<script setup lang="ts">
import { computed } from 'vue'

import type { FavoriteFixtureRecord } from '@/api/favorites'
import type { ResultFixture } from '@/api/fixtures'
import FavoriteButton from '@/components/FavoriteButton.vue'
import ResultPredictionSummary from '@/components/ResultPredictionSummary.vue'
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
}>(), {
  oddsClickable: false,
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

function openDetail() {
  emit('openDetail', props.fixture.fixture_id)
}
</script>

<template>
  <article class="result-fixture-card">
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
      <button
        type="button"
        class="score-btn"
        :aria-label="`查看 ${homeName} 对 ${awayName} 详情`"
        @click="openDetail"
      >
        {{ scoreText }}
      </button>
      <span class="team away">{{ awayName }}</span>
    </div>
    <p v-if="extraScoreLine" class="score-extra">{{ extraScoreLine }}</p>

    <ResultPredictionSummary
      :fixture="fixture"
      :odds-clickable="oddsClickable"
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

.score-extra {
  margin: -4px 0 0;
  text-align: center;
  font-size: 11px;
  color: var(--fa-text-secondary);
}
</style>
