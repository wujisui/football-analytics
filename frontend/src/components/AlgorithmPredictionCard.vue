<script setup lang="ts">
import { NCard } from 'naive-ui'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { FixtureResponse } from '@/api/types'
import FavoriteButton from '@/components/FavoriteButton.vue'
import FixtureMatchup from '@/components/FixtureMatchup.vue'
import PredictionRecommendationRow from '@/components/PredictionRecommendationRow.vue'
import { autoFavoriteMarket } from '@/composables/useFavoriteFixtures'
import { useFixturesShell } from '@/layouts/composables/useFixturesShell'
import {
  formatOdd,
  formatTime,
  hasRealProbabilities,
  leagueTagColor,
  toPercent,
} from '@/utils/format'
import { fixtureDetailRoute, type DetailFrom } from '@/utils/detailNav'
import { leagueLabel } from '@/utils/leagueNames'
import { snapshotFromAnalysis, type PredictionSnapshot } from '@/utils/opinionAdjust'
import { ahLinesOf, oddsSnippetFromFixture } from '@/utils/oddsDisplay'

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
const { selectedLeagueId, selectLeague } = useFixturesShell()

const resolvedFixtureId = computed(
  () => props.fixture?.fixture_id ?? props.fixtureId ?? null,
)

const pickMarket = computed(
  () => props.highlightMarket ?? autoFavoriteMarket(resolvedFixtureId.value),
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

const ahLines = computed(() => {
  if (!props.standalone || !props.fixture) return []
  return ahLinesOf(oddsSnippetFromFixture(props.fixture)?.asian_handicap)
})
const primaryAh = computed(() => ahLines.value[0] ?? null)
const ahExtraCount = computed(() => Math.max(0, ahLines.value.length - 1))
const primaryHomeOdd = computed(() =>
  primaryAh.value ? formatOdd(primaryAh.value.home) : '—',
)
const primaryAwayOdd = computed(() =>
  primaryAh.value ? formatOdd(primaryAh.value.away) : '—',
)
const primaryLine = computed(() => primaryAh.value?.line || '—')

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
  selectLeague(next)
  if (FIXTURES_ROUTES.has(String(route.name))) return
  const target = props.from === 'results' ? 'results' : 'predictions'
  void router.push({
    name: target,
    query: next == null ? {} : { league: String(next) },
  })
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
      <FixtureMatchup
        class="head-matchup"
        clickable
        :home-name="homeName"
        :away-name="awayName"
        :home-rank="fixture?.home_rank"
        :away-rank="fixture?.away_rank"
        @click="goStats"
      />
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
      class="prob-row"
      :class="{ 'odds-clickable': oddsClickable }"
      :role="oddsClickable ? 'button' : undefined"
      :tabindex="oddsClickable ? 0 : undefined"
      @click.stop="onOddsClick"
      @keydown.enter.prevent="onOddsClick"
      @keydown.space.prevent="onOddsClick"
    >
      <div v-for="p in probs" :key="p.key" class="prob-item">
        <span class="prob-head">
          <span>{{ p.label }}</span>
          <strong>{{ toPercent(p.value) }}</strong>
        </span>
        <div
          class="prob-bar"
          :class="{ slim: standalone }"
          :aria-hidden="true"
        >
          <span
            class="prob-bar-fill"
            :style="{ width: `${Math.round(p.value * 100)}%` }"
          />
        </div>
      </div>
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

    <div v-if="standalone" class="handicap-line" @click.stop>
      <span class="handicap-label">让球：</span>
      <div v-if="primaryAh" class="handicap-values">
        <span class="handicap-odd">{{ primaryHomeOdd }}</span>
        <n-popover
          v-if="ahExtraCount > 0"
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
              :aria-label="`主盘 ${primaryLine}，另有 ${ahExtraCount} 条让球盘，点击查看详情`"
              @click="goPredictionDetail"
            >
              {{ primaryLine }}
            </button>
          </template>
          <div class="ah-popover-panel">
            <div class="ah-popover-row ah-popover-head">
              <span class="ah-popover-label">让球</span>
              <span class="ah-popover-col">主队</span>
              <span class="ah-popover-col mid">盘口</span>
              <span class="ah-popover-col">客队</span>
            </div>
            <div
              v-for="(line, idx) in ahLines"
              :key="`ah-pop-${line.line}-${idx}`"
              class="ah-popover-row"
            >
              <span class="ah-popover-label" />
              <span class="ah-popover-col">{{ formatOdd(line.home) }}</span>
              <span class="ah-popover-col mid line">{{ line.line || '—' }}</span>
              <span class="ah-popover-col">{{ formatOdd(line.away) }}</span>
            </div>
          </div>
        </n-popover>
        <button
          v-else
          type="button"
          class="handicap-mid plain"
          aria-label="查看盘口详情"
          @click="goPredictionDetail"
        >
          {{ primaryLine }}
        </button>
        <span class="handicap-odd">{{ primaryAwayOdd }}</span>
      </div>
      <span v-else class="handicap-empty">暂无盘口</span>
    </div>

    <PredictionRecommendationRow
      :recommendation="prediction.recommendation"
      :handicap-lean="prediction.handicap_lean"
      :goal-lean="prediction.goal_lean"
      :both-score="prediction.both_score_lean"
      :score-hint="prediction.score_hint"
      :highlight-market="pickMarket"
      clickable
      @open="goBriefing"
    />
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
  border-radius: 4px;
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

.prob-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.odds-clickable {
  padding: 4px;
  margin: -4px;
  border-radius: 6px;
  cursor: pointer;
}

.odds-clickable:hover,
.odds-clickable:focus-visible {
  outline: none;
  background: var(--fa-bg-elevated);
}

.prob-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.prob-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px;
  font-size: 11px;
  line-height: 1.2;
  color: var(--fa-text-faint);
}

.prob-head strong {
  color: var(--fa-text-strong);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.prob-bar {
  height: 8px;
  border-radius: 999px;
  background: var(--fa-bg-elevated);
  overflow: hidden;
}

.prob-bar.slim {
  height: 6px;
}

.prob-bar-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--fa-highlight-text);
}

.handicap-line {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 4px 8px;
  border-radius: 4px;
  background: var(--fa-bg-elevated);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.handicap-values {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
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

.handicap-mid.plain {
  text-decoration: none;
}

.handicap-mid:hover,
.handicap-mid:focus-visible {
  background: var(--fa-bg-elevated);
  border-radius: 2px;
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

.predict-card.standalone .prob-item {
  gap: 4px;
}

.predict-card.standalone .prob-head {
  gap: 2px;
}

.predict-card.standalone .prob-head strong {
  font-size: 14px;
  font-weight: 700;
}
</style>
