<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { FavoriteFixtureRecord } from '@/api/favorites'
import type { ResultFixture } from '@/api/fixtures'
import type { FixtureResponse } from '@/api/types'
import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FavoriteButton from '@/components/FavoriteButton.vue'
import ResultPredictionSummary from '@/components/ResultPredictionSummary.vue'
import ScoreDetailLink from '@/components/ScoreDetailLink.vue'
import {
  formatDate,
  formatTime,
  leagueTagColor,
  resultStatusTagType,
  statusLabel,
  statusTagType,
} from '@/utils/format'
import { fixtureDetailRoute, type DetailFrom } from '@/utils/detailNav'
import { leagueLabel } from '@/utils/leagueNames'
import {
  resultExtraScoreLine,
  resultScoreText,
} from '@/utils/resultsDisplay'
import type { PredictionSnapshot } from '@/utils/opinionAdjust'
import type { ResultsHitKey } from '@/utils/resultsPageState'
import { useFixturesShell } from '@/layouts/composables/useFixturesShell'

const props = withDefaults(defineProps<{
  fixture: FixtureResponse | ResultFixture | FavoriteFixtureRecord
  prematch?: boolean
  predictionSnapshot?: PredictionSnapshot
  oddsClickable?: boolean
  showProbabilities?: boolean
  showDate?: boolean
  from?: DetailFrom
  date?: string | null
  hitFilterable?: boolean
  activeHitKey?: ResultsHitKey | null
}>(), {
  prematch: false,
  oddsClickable: false,
  showProbabilities: false,
  showDate: true,
  from: 'results',
  date: null,
  hitFilterable: false,
  activeHitKey: null,
})

const emit = defineEmits<{
  openDetail: [fixtureId: number]
  openOdds: []
  filterHit: [key: ResultsHitKey]
}>()

const router = useRouter()
const route = useRoute()
const { selectedLeagueId, selectLeague } = useFixturesShell()
const isPrematch = computed(() => props.prematch || 'analysis' in props.fixture)
const prematchFixture = computed(() =>
  'analysis' in props.fixture ? (props.fixture as FixtureResponse) : undefined,
)
const settledFixture = computed(() =>
  isPrematch.value
    ? undefined
    : (props.fixture as ResultFixture | FavoriteFixtureRecord),
)
const homeName = computed(() => props.fixture.home_team_name || '—')
const awayName = computed(() => props.fixture.away_team_name || '—')
const leagueName = computed(() => leagueLabel(props.fixture.league_name))
const kickoffText = computed(() => {
  const time = formatTime(props.fixture.fixture_date)
  return props.showDate
    ? `${formatDate(props.fixture.fixture_date)} ${time}`
    : time
})
const scoreText = computed(() => resultScoreText(props.fixture))
const extraScoreLine = computed(() => resultExtraScoreLine(props.fixture))
const statusShort = computed(() =>
  'status_short' in props.fixture ? props.fixture.status_short : undefined,
)
const resultFixturePayload = computed(() =>
  settledFixture.value && 'home_team_id' in settledFixture.value
    ? (settledFixture.value as ResultFixture)
    : undefined,
)
const denseBody = computed(
  () =>
    isPrematch.value
    || (
      props.showProbabilities
      && 'probabilities_available' in props.fixture
      && !!props.fixture.probabilities_available
    ),
)

function openDetail() {
  emit('openDetail', props.fixture.fixture_id)
}

function openStats() {
  void router.push(
    fixtureDetailRoute(props.fixture.fixture_id, {
      from: props.from,
      tab: 'record',
      date: props.date,
    }),
  )
}

const FIXTURES_ROUTES = new Set(['predictions', 'results'])

/** Filter the shell list to this league (toggle off if already selected). */
function onLeagueClick(e: Event) {
  e.stopPropagation()
  const id = Number(props.fixture.league_id)
  if (!Number.isFinite(id)) return
  const next = selectedLeagueId.value === id ? null : id
  selectLeague(next)
  if (FIXTURES_ROUTES.has(String(route.name))) return
  const target = props.from === 'results' ? 'results' : 'predictions'
  void router.push({
    name: target,
    query: next == null ? {} : { league: String(next) },
  })
}
</script>

<template>
  <n-card
    size="small"
    :bordered="false"
    class="result-fixture-card"
    :class="{ dense: denseBody, prematch: isPrematch }"
  >
    <FavoriteButton
      class="card-fav"
      :fixture-id="fixture.fixture_id"
      :fixture="prematchFixture"
      :result-fixture="resultFixturePayload"
      size="tiny"
    />
    <header class="card-head">
      <n-tag
        class="league-tag"
        :class="{ active: selectedLeagueId === fixture.league_id }"
        size="small"
        :bordered="false"
        role="button"
        tabindex="0"
        :aria-label="`筛选联赛 ${leagueName}`"
        :aria-pressed="selectedLeagueId === fixture.league_id"
        :color="{
          color: `${leagueTagColor(fixture.league_id)}18`,
          textColor: leagueTagColor(fixture.league_id),
        }"
        @click="onLeagueClick"
        @keydown.enter.prevent="onLeagueClick"
        @keydown.space.prevent="onLeagueClick"
      >
        {{ leagueName }}
      </n-tag>
      <span class="kickoff">
        {{ kickoffText }}
      </span>
      <n-tag
        size="small"
        :type="
          isPrematch
            ? statusTagType(fixture.status || '', statusShort, fixture.fixture_date)
            : resultStatusTagType(
                fixture.status || '',
                statusShort,
                fixture.fixture_date,
              )
        "
        :bordered="false"
      >
        {{ statusLabel(fixture.status || '', statusShort, fixture.fixture_date) }}
      </n-tag>
    </header>

    <n-button
      v-if="isPrematch"
      text
      type="primary"
      class="matchup matchup-link"
      @click="openStats"
    >
      <span class="team home">{{ homeName }}</span>
      <span class="versus">vs</span>
      <span class="team away">{{ awayName }}</span>
    </n-button>
    <div v-else class="matchup">
      <span class="team home">{{ homeName }}</span>
      <ScoreDetailLink
        class="score"
        :label="scoreText"
        @click="openDetail"
      />
      <span class="team away">{{ awayName }}</span>
    </div>
    <p v-if="!isPrematch && extraScoreLine" class="score-extra">{{ extraScoreLine }}</p>

    <AlgorithmPredictionCard
      v-if="isPrematch"
      class="predict-body"
      :fixture="prematchFixture"
      :snapshot="predictionSnapshot"
      :show-matchup-title="false"
      flush
      :odds-clickable="oddsClickable"
      :from="from"
      :date="date"
      @open-odds="emit('openOdds')"
    />
    <ResultPredictionSummary
      v-else-if="settledFixture"
      :fixture="settledFixture"
      :odds-clickable="oddsClickable"
      :show-probabilities="showProbabilities"
      :hit-filterable="hitFilterable"
      :active-hit-key="activeHitKey"
      @open-odds="emit('openOdds')"
      @filter-hit="emit('filterHit', $event)"
    />
  </n-card>
</template>

<style scoped>
.result-fixture-card {
  position: relative;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  background: var(--fa-bg-soft);
  overflow: hidden;
}

.result-fixture-card :deep(.n-card-content) {
  display: grid;
  grid-auto-flow: row;
  align-content: start;
  gap: 8px;
  padding: 8px 10px;
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

.result-fixture-card.dense {
  height: 100%;
}

.result-fixture-card.dense :deep(.n-card-content) {
  height: 100%;
}

.result-fixture-card.prematch :deep(.n-card-content) {
  grid-template-rows: auto auto minmax(0, 1fr);
}

.card-fav {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 1;
}

.card-head {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 6px;
  /* Keep status clear of the absolute favorite control. */
  padding-right: 26px;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
}

.league-tag {
  flex: 0 1 auto;
  min-width: 0;
  max-width: 42%;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.league-tag.active {
  box-shadow: inset 0 0 0 1px currentColor;
}

:deep(.league-tag .n-tag__content) {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kickoff {
  flex: 1 1 0;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--fa-text-secondary);
}

.card-head > :deep(.n-tag) {
  flex-shrink: 0;
}

.matchup {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  font-weight: 600;
}

.matchup-link {
  display: flex;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  height: auto;
  padding: 0;
  white-space: normal;
}

:deep(.matchup-link .n-button__content) {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

.versus {
  flex-shrink: 0;
  color: var(--fa-text-strong);
}

.team {
  flex: 1 1 0;
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
  margin: 0;
  text-align: center;
  font-size: 11px;
  color: var(--fa-text-secondary);
}

.predict-body {
  min-height: 0;
}
</style>
