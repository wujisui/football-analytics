<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { FavoriteFixtureRecord } from '@/api/favorites'
import type { ResultFixture } from '@/api/fixtures'
import type { FixtureResponse } from '@/api/types'
import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import DetailTabHint from '@/components/DetailTabHint.vue'
import FavoriteButton from '@/components/FavoriteButton.vue'
import FixtureMatchup from '@/components/FixtureMatchup.vue'
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
import { isFixtureCardMarkClickIgnored } from '@/utils/fixtureCardMark'
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
  /** Auto-favorite market to highlight in the prediction tag row. */
  highlightMarket?: string | null
  from?: DetailFrom
  date?: string | null
  hitFilterable?: boolean
  activeHitKey?: ResultsHitKey | null
  /** 列表阅读标记：点卡片空白处选中/反选 */
  selectable?: boolean
  selected?: boolean
}>(), {
  prematch: false,
  oddsClickable: false,
  showProbabilities: false,
  showDate: true,
  highlightMarket: null,
  from: 'results',
  date: null,
  hitFilterable: false,
  activeHitKey: null,
  selectable: false,
  selected: false,
})

const emit = defineEmits<{
  openDetail: [fixtureId: number]
  openOdds: []
  filterHit: [key: ResultsHitKey]
  toggleSelect: [fixtureId: number]
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
const homeRank = computed(() =>
  'home_rank' in props.fixture ? props.fixture.home_rank ?? null : null,
)
const awayRank = computed(() =>
  'away_rank' in props.fixture ? props.fixture.away_rank ?? null : null,
)
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

/** 卡片内已有自己点击语义的控件（比分/联赛标签/命中标签/收藏）不触发标记 */
function onCardClick(e: MouseEvent) {
  if (!props.selectable) return
  if (isFixtureCardMarkClickIgnored(e)) return
  emit('toggleSelect', props.fixture.fixture_id)
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
    :class="{
      dense: denseBody,
      prematch: isPrematch,
      'fa-card-markable': selectable,
      'is-marked': selected,
    }"
    @click="onCardClick"
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
        <n-ellipsis style="max-width: 100%">{{ leagueName }}</n-ellipsis>
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

    <DetailTabHint v-if="isPrematch" tab="record">
      <FixtureMatchup
        clickable
        spread
        :home-name="homeName"
        :away-name="awayName"
        :home-rank="homeRank"
        :away-rank="awayRank"
        @click="openStats"
      />
    </DetailTabHint>
    <FixtureMatchup
      v-else
      spread
      :home-name="homeName"
      :away-name="awayName"
      :home-rank="homeRank"
      :away-rank="awayRank"
    >
      <template #middle>
        <ScoreDetailLink
          class="score"
          :label="scoreText"
          @click="openDetail"
        />
      </template>
    </FixtureMatchup>
    <p v-if="!isPrematch && extraScoreLine" class="score-extra">{{ extraScoreLine }}</p>

    <AlgorithmPredictionCard
      v-if="isPrematch"
      class="predict-body"
      :fixture="prematchFixture"
      :fixture-id="fixture.fixture_id"
      :snapshot="predictionSnapshot"
      :show-matchup-title="false"
      flush
      :odds-clickable="oddsClickable"
      :highlight-market="highlightMarket"
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
      :highlight-market="highlightMarket"
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

/* 列表翻阅定位样式见全局 .fa-card-markable */

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
  max-width: 100%;
}

.kickoff {
  display: inline-block;
  min-width: 0;
  font-size: 12px;
  color: var(--fa-text-secondary);
  user-select: none;
}

.card-head > :deep(.n-tag) {
  flex-shrink: 0;
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
