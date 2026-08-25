<script setup lang="ts">
import { NCard } from 'naive-ui'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { FixtureResponse } from '@/api/types'
import DetailTabHint from '@/components/DetailTabHint.vue'
import FavoriteButton from '@/components/FavoriteButton.vue'
import FixtureMatchup from '@/components/FixtureMatchup.vue'
import PredictionRecommendationRow from '@/components/PredictionRecommendationRow.vue'
import RecommendationQualityRate from '@/components/RecommendationQualityRate.vue'
import WdlProbabilityBars from '@/components/WdlProbabilityBars.vue'
import { favoriteQualityRating } from '@/composables/useFavoriteFixtures'
import {
  formatLocalMonthDayMinute,
  formatOdd,
  formatTime,
  hasRealProbabilities,
  leagueTagColor,
} from '@/utils/format'
import { fixtureDetailRoute, type DetailFrom } from '@/utils/detailNav'
import {
  fixturesShellContext,
  parseFixturesLeagueFilter,
  writeFixturesLeagueFilter,
} from '@/utils/fixturesLeagueFilter'
import { leagueLabel } from '@/utils/leagueNames'
import { snapshotFromAnalysis, type PredictionSnapshot } from '@/utils/opinionAdjust'
import {
  ahLinesOf,
  isOpeningDistinct,
  oddsSnippetFromFixture,
  openingOddsSnippetFromFixture,
} from '@/utils/oddsDisplay'

const props = withDefaults(
  defineProps<{
    fixture?: FixtureResponse
    snapshot?: PredictionSnapshot
    fixtureId?: number
    /** Elevated card for the desktop predictions list (includes handicap line). */
    standalone?: boolean
    /** League tag + centered matchup title. */
    showMatchupTitle?: boolean
    /** Parent card owns padding/background; render only the prediction content. */
    flush?: boolean
    /** Click win/draw/away bars to open pre-match odds (e.g. phone list). */
    oddsClickable?: boolean
    /** Override auto-favorite market highlight (favorites page passes row field). */
    highlightMarket?: string | null
    from?: DetailFrom
    date?: string | null
  }>(),
  {
    standalone: false,
    showMatchupTitle: true,
    flush: false,
    oddsClickable: false,
    highlightMarket: null,
    from: 'predictions',
    date: null,
  },
)

const emit = defineEmits<{
  openOdds: []
}>()

const router = useRouter()
const route = useRoute()
const selectedLeagueId = computed(() =>
  parseFixturesLeagueFilter(route.query.league),
)

const resolvedFixtureId = computed(
  () => props.fixture?.fixture_id ?? props.fixtureId ?? null,
)

const prediction = computed((): PredictionSnapshot => {
  if (props.snapshot) return props.snapshot
  if (props.fixture) return snapshotFromAnalysis(props.fixture.analysis)
  return {
    home_win_prob: 0,
    draw_prob: 0,
    away_win_prob: 0,
    recommendation: '待分析',
    goal_lean: '',
    both_score_lean: '',
    score_hint: '',
    handicap_lean: '',
    probabilitiesAvailable: false,
  }
})

const predictionReady = computed(() => {
  if (props.snapshot) return props.snapshot.probabilitiesAvailable
  if (!props.fixture) return false
  return hasRealProbabilities(
    props.fixture.analysis.probabilities,
    prediction.value.recommendation,
  )
})

const homeName = computed(() => props.fixture?.home_team_name || '—')
const awayName = computed(() => props.fixture?.away_team_name || '—')
const matchupText = computed(() => `${homeName.value} vs ${awayName.value}`)
const leagueName = computed(() => leagueLabel(props.fixture?.league_name))
const leagueId = computed(() => props.fixture?.league_id ?? null)
const leagueActive = computed(
  () => leagueId.value != null && selectedLeagueId.value === leagueId.value,
)
const leagueColor = computed(() =>
  leagueId.value != null ? leagueTagColor(leagueId.value) : undefined,
)
const kickoffText = computed(() =>
  props.fixture ? formatTime(props.fixture.fixture_date) : '',
)

const currentOdds = computed(() =>
  props.standalone && props.fixture ? oddsSnippetFromFixture(props.fixture) : null,
)
const openingOdds = computed(() =>
  props.standalone && props.fixture
    ? openingOddsSnippetFromFixture(props.fixture)
    : null,
)
const currentAhLines = computed(() => ahLinesOf(currentOdds.value?.asian_handicap))
const openingAhLines = computed(() => ahLinesOf(openingOdds.value?.asian_handicap))
const displayAhLines = computed(() =>
  currentAhLines.value.length ? currentAhLines.value : openingAhLines.value,
)
const primaryAh = computed(() => displayAhLines.value[0] ?? null)
const showCurrentBoard = computed(() => currentAhLines.value.length > 0)
/** Same capture time = 初盘 was just frozen from this board; show it as 即时盘 only. */
const showOpeningBoard = computed(
  () =>
    openingAhLines.value.length > 0
    && (!showCurrentBoard.value
      || isOpeningDistinct(openingOdds.value, currentOdds.value)),
)
const ahBoards = computed(() => {
  const boards = []
  if (showOpeningBoard.value) {
    boards.push({
      key: 'opening',
      label: '初盘',
      capturedAt: capturedAtText(openingOdds.value?.captured_at),
      lines: openingAhLines.value,
    })
  }
  if (showCurrentBoard.value) {
    boards.push({
      key: 'current',
      label: '即时盘',
      capturedAt: capturedAtText(currentOdds.value?.captured_at),
      lines: currentAhLines.value,
    })
  }
  return boards
})
const ahBoardsLabel = computed(() =>
  ahBoards.value.map((board) => board.label).join('与'),
)

function capturedAtText(at?: string | null): string {
  return at ? formatLocalMonthDayMinute(at) : ''
}
const primaryHomeOdd = computed(() =>
  primaryAh.value ? formatOdd(primaryAh.value.home) : '—',
)
const primaryAwayOdd = computed(() =>
  primaryAh.value ? formatOdd(primaryAh.value.away) : '—',
)
const primaryLine = computed(() => primaryAh.value?.line || '—')

/** 每日推荐质量：0.5–5 星，只有算法推荐场次才有。 */
const qualityRating = computed(() => favoriteQualityRating(resolvedFixtureId.value))

const probs = computed(() => {
  if (!predictionReady.value) return []
  return [
    { key: 'home', label: '主胜', value: prediction.value.home_win_prob },
    { key: 'draw', label: '平局', value: prediction.value.draw_prob },
    { key: 'away', label: '客胜', value: prediction.value.away_win_prob },
  ]
})

const FIXTURES_ROUTES = new Set(['predictions', 'results'])

function onLeagueClick(e: Event) {
  e.stopPropagation()
  const id = leagueId.value
  if (id == null || !Number.isFinite(id)) return
  const next = selectedLeagueId.value === id ? null : id
  const target = props.from === 'results' ? 'results' : 'predictions'
  const routeName = FIXTURES_ROUTES.has(String(route.name))
    ? String(route.name)
    : target
  writeFixturesLeagueFilter(next, fixturesShellContext(routeName))
  const location = {
    name: FIXTURES_ROUTES.has(String(route.name)) ? route.name : target,
    query: next == null ? {} : { league: String(next) },
  }
  if (FIXTURES_ROUTES.has(String(route.name))) void router.replace(location)
  else void router.push(location)
}

function goStats() {
  if (resolvedFixtureId.value == null) return
  void router.push(
    fixtureDetailRoute(resolvedFixtureId.value, {
      from: props.from,
      tab: 'record',
      date: props.date,
    }),
  )
}

function goBriefing() {
  if (resolvedFixtureId.value == null) return
  void router.push(
    fixtureDetailRoute(resolvedFixtureId.value, {
      from: props.from,
      tab: 'briefing',
      date: props.date,
    }),
  )
}

function goPredictionDetail(e?: Event) {
  e?.stopPropagation()
  if (resolvedFixtureId.value == null) return
  void router.push(
    fixtureDetailRoute(resolvedFixtureId.value, {
      from: props.from,
      tab: 'prediction',
      date: props.date,
    }),
  )
}

function onOddsClick() {
  if (!props.oddsClickable) return
  emit('openOdds')
}
</script>

<template>
  <component
    :is="standalone ? NCard : 'section'"
    class="predict-card"
    :class="{ standalone, zone: !standalone, flush }"
    :size="standalone ? 'small' : undefined"
    :bordered="standalone ? false : undefined"
  >
    <header v-if="showMatchupTitle" class="card-head">
      <div class="head-meta">
        <n-tag
          v-if="leagueId != null"
          class="league-tag"
          :class="{ active: leagueActive }"
          size="small"
          :bordered="false"
          role="button"
          tabindex="0"
          :aria-label="`筛选联赛 ${leagueName}`"
          :aria-pressed="leagueActive"
          :color="
            leagueColor
              ? { color: `${leagueColor}18`, textColor: leagueColor }
              : undefined
          "
          @click="onLeagueClick"
          @keydown.enter.prevent="onLeagueClick"
          @keydown.space.prevent="onLeagueClick"
        >
          <n-ellipsis style="max-width: 100%">{{ leagueName }}</n-ellipsis>
        </n-tag>
        <n-text v-if="kickoffText" depth="3" class="kickoff">
          {{ kickoffText }}
        </n-text>
      </div>
      <DetailTabHint tab="record" :text="matchupText">
        <FixtureMatchup
          class="head-matchup"
          clickable
          :name-tooltip="false"
          :home-name="homeName"
          :away-name="awayName"
          :home-rank="fixture?.home_rank"
          :away-rank="fixture?.away_rank"
          @click="goStats"
        />
      </DetailTabHint>
      <FavoriteButton
        v-if="fixture"
        class="card-fav"
        :fixture-id="fixture.fixture_id"
        :fixture="fixture"
        size="tiny"
      />
    </header>

    <div
      v-if="predictionReady"
      :class="{ 'odds-clickable': oddsClickable }"
      :role="oddsClickable ? 'button' : undefined"
      :tabindex="oddsClickable ? 0 : undefined"
      @click.stop="onOddsClick"
      @keydown.enter.prevent="onOddsClick"
      @keydown.space.prevent="onOddsClick"
    >
      <WdlProbabilityBars
        :items="probs"
        :variant="standalone ? 'card' : 'list'"
      />
    </div>
    <p
      v-else
      class="predict-empty"
      :class="{ 'odds-clickable': oddsClickable }"
      :role="oddsClickable ? 'button' : undefined"
      :tabindex="oddsClickable ? 0 : undefined"
      @click.stop="onOddsClick"
      @keydown.enter.prevent="onOddsClick"
      @keydown.space.prevent="onOddsClick"
    >
      暂无有效胜平负概率（缺近况或盘口）
    </p>

    <div
      v-if="standalone"
      class="handicap-line"
      :class="{ 'has-rate': qualityRating != null }"
      @click.stop
    >
      <span class="handicap-label">让球：</span>
      <div v-if="primaryAh" class="handicap-values">
        <span class="handicap-odd">{{ primaryHomeOdd }}</span>
        <n-popover
          trigger="hover"
          placement="bottom"
          :show-arrow="false"
          :delay="120"
          raw
        >
          <template #trigger>
            <button
              type="button"
              class="handicap-mid"
              :aria-label="`让球主盘 ${primaryLine}，悬停查看${ahBoardsLabel}，点击查看详情`"
              @click="goPredictionDetail"
            >
              {{ primaryLine }}
            </button>
          </template>
          <div class="ah-board-popover">
            <section
              v-for="board in ahBoards"
              :key="board.key"
              class="ah-popover-panel"
            >
              <h4 class="ah-board-title">
                {{ board.label }}
                <span v-if="board.capturedAt" class="ah-board-time">
                  {{ board.capturedAt }}
                </span>
              </h4>
              <div class="ah-popover-row ah-popover-head">
                <span class="ah-popover-col">主队</span>
                <span class="ah-popover-col mid">盘口</span>
                <span class="ah-popover-col">客队</span>
              </div>
              <div
                v-for="(line, idx) in board.lines"
                :key="`${board.key}-${line.line}-${idx}`"
                class="ah-popover-row"
              >
                <span class="ah-popover-col">{{ formatOdd(line.home) }}</span>
                <span class="ah-popover-col mid line">{{ line.line || '—' }}</span>
                <span class="ah-popover-col">{{ formatOdd(line.away) }}</span>
              </div>
            </section>
          </div>
        </n-popover>
        <span class="handicap-odd">{{ primaryAwayOdd }}</span>
      </div>
      <span v-else class="handicap-empty">暂无盘口</span>
      <RecommendationQualityRate :value="qualityRating" />
    </div>

    <DetailTabHint tab="briefing">
      <PredictionRecommendationRow
        :recommendation="prediction.recommendation"
        :handicap-lean="prediction.handicap_lean"
        :goal-lean="prediction.goal_lean"
        :both-score="prediction.both_score_lean"
        :score-hint="prediction.score_hint"
        :fixture-id="resolvedFixtureId"
        :highlight-market="highlightMarket"
        clickable
        @open="goBriefing"
      />
    </DetailTabHint>
  </component>
</template>

<style scoped>
.predict-card {
  min-width: 0;
  box-sizing: border-box;
}

.predict-card.zone {
  display: grid;
  grid-auto-flow: row;
  align-content: space-between;
  gap: 6px;
  background: var(--fa-bg-soft);
  border-radius: var(--fa-radius-card);
  padding: 12px;
  height: 100%;
}

.predict-card.zone.flush {
  padding: 0;
  border-radius: 0;
  background: transparent;
}

.predict-card.standalone {
  height: 100%;
  overflow: hidden;
  background: var(--fa-bg-soft);
}

.predict-card.standalone :deep(.n-card-content) {
  display: grid;
  grid-template-rows: auto auto auto auto;
  align-content: space-between;
  gap: 6px;
  height: 100%;
  padding: 8px;
  box-sizing: border-box;
}

.card-head {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-width: 0;
  min-height: 28px;
}

.head-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.league-tag {
  position: relative;
  z-index: 1;
  max-width: 88px;
  cursor: pointer;
}

.kickoff {
  flex-shrink: 0;
  font-size: 12px;
  white-space: nowrap;
  user-select: none;
}

.league-tag.active {
  outline: 1px solid currentColor;
}

.league-tag :deep(.n-tag__content) {
  display: block;
  min-width: 0;
  max-width: 100%;
}

.head-matchup {
  min-width: 0;
  text-align: center;
}

.card-fav {
  justify-self: end;
}

.odds-clickable {
  padding: 4px;
  margin: -4px;
  border-radius: var(--fa-radius-card);
  cursor: pointer;
}

.odds-clickable:hover,
.odds-clickable:focus-visible {
  outline: none;
  background: var(--fa-bg-elevated);
}

.handicap-line {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 4px 8px;
  border-radius: var(--fa-radius-card);
  background: var(--fa-bg-elevated);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

/* 有星级时让球数字收紧靠左，把右侧让给星级 */
.handicap-line.has-rate {
  grid-template-columns: auto minmax(0, auto) minmax(0, 1fr);
}

.handicap-values {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
}

.handicap-line.has-rate .handicap-values {
  justify-content: flex-start;
  gap: 6px;
}

.handicap-line :deep(.quality-rate) {
  justify-self: end;
}

.handicap-label {
  color: var(--fa-text-secondary);
  font-weight: 500;
}

.handicap-odd {
  color: var(--fa-text);
  font-weight: 600;
}

.handicap-mid {
  appearance: none;
  margin: 0;
  padding: 0 2px;
  border: none;
  background: none;
  font: inherit;
  font-weight: 700;
  color: var(--fa-text-strong);
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
  text-underline-offset: 3px;
}

.handicap-mid:hover,
.handicap-mid:focus-visible {
  background: var(--fa-bg-elevated);
  border-radius: var(--fa-radius-card);
  outline: none;
}

.handicap-empty {
  color: var(--fa-text-faint);
  font-size: 12px;
}

.predict-empty {
  margin: 0;
  font-size: 13px;
  color: var(--fa-text-faint);
}

</style>
