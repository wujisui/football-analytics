<script setup lang="ts">
import { computed, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'

import type { FixtureResponse } from '@/api/types'
import FavoriteButton from '@/components/FavoriteButton.vue'
import FixtureMatchup from '@/components/FixtureMatchup.vue'
import PredictionRecommendationRow from '@/components/PredictionRecommendationRow.vue'
import PreMatchOddsModal from '@/components/PreMatchOddsModal.vue'
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
const rows = computed(() => buildMarketRows(props.fixture))
const prediction = computed(() => snapshotFromAnalysis(props.fixture.analysis))

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
  // 卡片在 keep-alive 列表里不卸载：不还原就会一直停在 opening 态，返回后点不动
  openingDetail.value = true
  void router
    .push(
      fixtureDetailRoute(props.fixture.fixture_id, {
        from: 'predictions',
        tab: 'record',
      }),
    )
    .finally(() => {
      openingDetail.value = false
    })
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
      <div class="market-board">
        <div
          v-for="row in rows"
          :key="row.market"
          class="market-column"
        >
          <n-text class="market-title">{{ row.title }}</n-text>
          <div class="pick-cells">
            <n-button
              v-for="cell in row.cells"
              :key="`${cell.market}-${cell.outcome}`"
              block
              size="small"
              :type="selected(cell) ? 'primary' : 'default'"
              secondary
              :disabled="cell.disabled || cell.odd == null"
              class="odd-button"
              :class="{ inline: row.market === 'spf', 'is-selected': selected(cell) }"
              @click="onPick(cell)"
            >
              <span class="pick-label">{{ cell.displayLabel }}</span>
              <span class="pick-odd">{{ cell.odd ?? '—' }}</span>
            </n-button>
          </div>
        </div>
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
      :reference-market="fixture.reference_market"
      :reference-lean="fixture.reference_lean"
      :reference-probability="fixture.reference_probability"
      :fixture-id="fixture.fixture_id"
      clickable
      @open="showOddsModal = true"
    />
  </n-card>

  <PreMatchOddsModal
    v-if="isPhone"
    v-model:show="showOddsModal"
    :odds="fixture.odds_snippet"
    :fixture-id="fixture.fixture_id"
    from="predictions"
  />
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
  display: flex;
  min-height: 100%;
  overflow: hidden;
}

.market-board {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 7px;
  width: 100%;
  height: 100%;
  min-height: 0;
  box-sizing: border-box;
}

.market-column {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 5px;
  min-width: 0;
  min-height: 0;
}

.market-title {
  overflow: hidden;
  font-size: 12px;
  line-height: 18px;
  text-align: center;
  white-space: nowrap;
  text-overflow: ellipsis;
  user-select: none;
}

.pick-cells {
  display: grid;
  grid-auto-rows: minmax(0, 1fr);
  gap: 5px;
  min-height: 0;
}

.odd-button {
  height: 100%;
  min-height: 0;
  padding: 2px 3px;
  font-variant-numeric: tabular-nums;
}

.odd-button :deep(.n-button__content) {
  display: flex;
  flex-direction: column;
  gap: 1px;
  line-height: 1.15;
}

/* 独赢一列有三行，横排「文案/赔率」居中，中间斜杠当分隔。 */
.odd-button.inline :deep(.n-button__content) {
  flex-direction: row;
  justify-content: center;
  align-items: center;
  gap: 0;
}

.odd-button.inline .pick-label::after {
  content: '/';
}

.pick-label,
.pick-odd {
  overflow: hidden;
  max-width: 100%;
  font-size: 12px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* 未选中：玩法名退一档，和赔率拉开层级。选中态按钮本身已是高亮块，
   再压一次文字颜色反差过大，沿用按钮自带文字色。 */
.odd-button:not(.is-selected) .pick-label {
  color: var(--fa-text-secondary);
}

.pick-odd {
  color: inherit;
  font-weight: 600;
}

.calc-fixture.phone .market-board {
  gap: 6px;
}
</style>
