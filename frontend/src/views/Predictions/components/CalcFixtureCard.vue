<script setup lang="ts">
import { computed, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'

import type { FixtureResponse } from '@/api/types'
import FavoriteButton from '@/components/FavoriteButton.vue'
import FixtureMatchup from '@/components/FixtureMatchup.vue'
import PredictionRecommendationRow from '@/components/PredictionRecommendationRow.vue'
import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import { useIsPhone } from '@/composables/useMediaQuery'
import { snapshotFromAnalysis } from '@/utils/opinionAdjust'
import { useBetCalculator } from '@/views/Predictions/composables/useBetCalculator'
import { buildMarketRows, type CalcCell } from '@/utils/betCalculator'
import { fixtureDetailRoute } from '@/utils/detailNav'
import { formatTime, leagueTagColor } from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'

const props = defineProps<{
  fixture: FixtureResponse
}>()

const message = useMessage()
const router = useRouter()
const isPhone = useIsPhone()
const showOddsModal = ref(false)
const openingDetail = ref(false)
const { isSelected, toggleCell } = useBetCalculator()

const rows = computed(() =>
  buildMarketRows(props.fixture, { combineOuBtts: isPhone.value }),
)
const prediction = computed(() => snapshotFromAnalysis(props.fixture.analysis))
const marketGap = computed(() => (isPhone.value ? 8 : 6))

const leagueName = computed(() => leagueLabel(props.fixture.league_name))
const leagueColor = computed(() => leagueTagColor(props.fixture.league_id))
const kickoffText = computed(() => formatTime(props.fixture.fixture_date))

function onPick(cell: CalcCell) {
  const err = toggleCell(props.fixture, cell)
  if (err) message.warning(err)
}

function selected(cell: CalcCell): boolean {
  return isSelected(props.fixture.fixture_id, cell)
}

function goDetail() {
  if (openingDetail.value) return
  openingDetail.value = true
  void router.push(
    fixtureDetailRoute(props.fixture.fixture_id, {
      from: 'predictions',
      tab: 'record',
    }),
  )
}
</script>

<template>
  <n-card
    size="small"
    :bordered="false"
    class="calc-fixture"
    :class="{ phone: isPhone }"
  >
    <!-- Desktop pairs this card with AlgorithmPredictionCard, which already
         carries league / kickoff / matchup / favorite. -->
    <div v-if="isPhone" class="fixture-meta">
      <div class="meta-left">
        <n-ellipsis class="league" :style="{ color: leagueColor }">
          {{ leagueName }}
        </n-ellipsis>
        <n-text depth="3" class="kickoff">{{ kickoffText }}</n-text>
      </div>
      <FixtureMatchup
        class="meta-matchup"
        clickable
        :opening="openingDetail"
        :home-name="fixture.home_team_name || '—'"
        :away-name="fixture.away_team_name || '—'"
        :home-rank="fixture.home_rank"
        :away-rank="fixture.away_rank"
        @click="goDetail"
      />
      <FavoriteButton
        class="fav"
        :fixture-id="fixture.fixture_id"
        :fixture="fixture"
        size="tiny"
      />
    </div>

    <div class="market-list">
      <div class="market-rows">
        <n-grid
          v-for="row in rows"
          :key="row.market"
          :cols="5"
          :x-gap="marketGap"
          class="market-row"
        >
          <n-gi>
            <n-text depth="2" class="play-label">{{ row.playLabel }}</n-text>
          </n-gi>
          <n-gi :span="4" class="pick-cells">
            <n-grid
              :cols="row.cells.length"
              :x-gap="marketGap"
              class="pick-grid"
            >
              <n-gi
                v-for="cell in row.cells"
                :key="`${cell.market}-${cell.outcome}`"
              >
                <n-button
                  block
                  size="small"
                  :type="selected(cell) ? 'warning' : 'default'"
                  :secondary="!selected(cell)"
                  :disabled="cell.disabled || cell.odd == null"
                  class="odd-button"
                  @click="onPick(cell)"
                >
                  <n-flex :wrap="false" align="center" justify="center" :size="4">
                    <n-text>{{ cell.pickLabel.split(' ')[0] }}</n-text>
                    <n-text depth="3">/</n-text>
                    <n-text strong>{{ cell.odd ?? '—' }}</n-text>
                  </n-flex>
                </n-button>
              </n-gi>
            </n-grid>
          </n-gi>
        </n-grid>
      </div>
    </div>

    <PredictionRecommendationRow
      v-if="isPhone"
      class="phone-recommendation"
      :recommendation="prediction.recommendation"
      :handicap-lean="prediction.handicap_lean"
      :goal-lean="prediction.goal_lean"
      :both-score="prediction.both_score_lean"
      :score-hint="prediction.score_hint"
      :fixture-id="fixture.fixture_id"
      clickable
      @open="showOddsModal = true"
    />
  </n-card>

  <n-modal
    v-if="isPhone"
    v-model:show="showOddsModal"
    preset="card"
    title="赛前盘口"
    to="body"
    :auto-focus="false"
    :style="{ width: 'min(360px, calc(100vw - 24px))' }"
    :segmented="{ content: true, footer: false }"
  >
    <PreMatchOddsTable
      :odds="fixture.odds_snippet"
      link-middle-to-detail
      :fixture-id="fixture.fixture_id"
      from="predictions"
    />
  </n-modal>
</template>

<style scoped>
.calc-fixture {
  height: 100%;
  overflow: hidden;
  background: var(--fa-bg-soft);
}

.calc-fixture :deep(.n-card-content) {
  display: grid;
  grid-template-rows: minmax(0, 1fr);
  gap: 6px;
  height: 100%;
  min-height: 0;
  padding: 8px;
  box-sizing: border-box;
  overflow: hidden;
}

.calc-fixture.phone :deep(.n-card-content) {
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 4px;
  padding: 6px 8px;
}

.phone-recommendation {
  max-height: 40px;
  overflow: hidden;
  font-size: 12px;
}

/* League+time stay left; matchup fills the rest (no overlap with long names). */
.fixture-meta {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.meta-left {
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 7.5em;
  min-width: 0;
  overflow: hidden;
}

.meta-matchup {
  justify-self: stretch;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

.league {
  flex: 1 1 auto;
  max-width: 4.5em;
  min-width: 0;
  font-weight: 600;
}

.kickoff {
  flex: 0 0 auto;
  font-size: 12px;
  white-space: nowrap;
}

.fav {
  flex-shrink: 0;
}

.market-list {
  min-height: 100%;
  overflow: hidden;
}

.market-rows {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 6px;
  height: 100%;
  min-height: 0;
}

.calc-fixture.phone .market-rows {
  gap: 4px;
}

.market-row {
  align-items: center;
}

/* Fill leftover card height so pick targets grow without raising item-size. */
.calc-fixture.phone .market-row {
  flex: 1 1 0;
  min-height: 0;
}

.calc-fixture.phone .market-row :deep(.n-grid),
.calc-fixture.phone .pick-grid {
  height: 100%;
  align-items: stretch;
}

.calc-fixture.phone .pick-cells,
.calc-fixture.phone .pick-cells :deep(.n-grid-item) {
  height: 100%;
  min-height: 0;
  display: flex;
}

.calc-fixture.phone .pick-cells :deep(.n-grid-item) > * {
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
}

.play-label {
  display: flex;
  align-items: center;
  font-size: 12px;
  line-height: 1.2;
  height: 100%;
  padding-left: 2px;
  word-break: keep-all;
}

.odd-button {
  font-variant-numeric: tabular-nums;
}

.odd-button :deep(.n-text) {
  color: inherit;
  font-size: 12px;
}

.calc-fixture.phone .odd-button {
  height: 100%;
  min-height: 0;
}
</style>
