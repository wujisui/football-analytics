<script setup lang="ts">
import { computed } from 'vue'
import { useMessage } from 'naive-ui'

import type { FixtureResponse } from '@/api/types'
import PredictionRecommendationRow from '@/components/PredictionRecommendationRow.vue'
import { useIsPhone } from '@/composables/useMediaQuery'
import { snapshotFromAnalysis } from '@/utils/opinionAdjust'
import { useBetCalculator } from '@/views/Predictions/composables/useBetCalculator'
import { buildMarketRows, type CalcCell } from '@/utils/betCalculator'
import { formatDate, formatTime, leagueTagColor } from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'

const props = defineProps<{
  fixture: FixtureResponse
}>()

const message = useMessage()
const isPhone = useIsPhone()
const { isSelected, toggleCell } = useBetCalculator()

const rows = computed(() =>
  buildMarketRows(props.fixture, { combineOuBtts: isPhone.value }),
)
const prediction = computed(() => snapshotFromAnalysis(props.fixture.analysis))

const leagueName = computed(() => leagueLabel(props.fixture.league_name))
const leagueColor = computed(() => leagueTagColor(props.fixture.league_id))
const kickoffText = computed(
  () =>
    `${formatDate(props.fixture.fixture_date)} ${formatTime(props.fixture.fixture_date)}`,
)

function onPick(cell: CalcCell) {
  const err = toggleCell(props.fixture, cell)
  if (err) message.warning(err)
}

function selected(cell: CalcCell): boolean {
  return isSelected(props.fixture.fixture_id, cell)
}
</script>

<template>
  <n-card
    size="small"
    :bordered="false"
    class="calc-fixture"
    :class="{ phone: isPhone }"
  >
    <n-flex :wrap="false" align="center" :size="8" class="fixture-meta">
      <n-text strong class="league" :style="{ color: leagueColor }">
        {{ leagueName }}
      </n-text>
      <n-flex :wrap="false" justify="center" align="center" :size="6" class="matchup">
        <n-ellipsis>{{ fixture.home_team_name || '—' }}</n-ellipsis>
        <n-text depth="3" class="versus">VS</n-text>
        <n-ellipsis>{{ fixture.away_team_name || '—' }}</n-ellipsis>
      </n-flex>
      <n-text depth="3" class="kickoff">{{ kickoffText }}</n-text>
    </n-flex>

    <div v-nested-scroll class="market-list">
      <n-flex vertical :size="8">
        <n-grid
        v-for="row in rows"
          :key="row.market"
          :cols="5"
          :x-gap="6"
          class="market-row"
        >
          <n-gi>
            <n-text depth="2" class="play-label">{{ row.playLabel }}</n-text>
          </n-gi>
          <n-gi :span="4">
            <n-grid :cols="row.cells.length" :x-gap="6">
              <n-gi
                v-for="cell in row.cells"
                :key="`${cell.market}-${cell.outcome}`"
              >
                <n-button
                  block
                  size="tiny"
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
      </n-flex>
    </div>

    <PredictionRecommendationRow
      v-if="isPhone"
      class="phone-recommendation"
      :recommendation="prediction.recommendation"
      :handicap-lean="prediction.handicap_lean"
      :goal-lean="prediction.goal_lean"
      :both-score="prediction.both_score_lean"
      :score-hint="prediction.score_hint"
    />
  </n-card>
</template>

<style scoped>
.calc-fixture {
  height: 100%;
  overflow: hidden;
  background: var(--fa-bg-soft);
}

.calc-fixture :deep(.n-card-content) {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 6px;
  height: 100%;
  min-height: 0;
  padding: 8px;
  box-sizing: border-box;
  overflow: hidden;
}

.calc-fixture.phone :deep(.n-card-content) {
  grid-template-rows: auto minmax(0, 1fr) auto;
}

.phone-recommendation {
  max-height: 52px;
  overflow-x: hidden;
  overflow-y: auto;
  font-size: 12px;
  -webkit-overflow-scrolling: touch;
}

.league {
  flex: 0 1 auto;
  min-width: 48px;
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.matchup {
  flex: 1;
  min-width: 0;
  font-size: 13px;
}

.matchup :deep(.n-ellipsis) {
  flex: 0 1 auto;
  min-width: 0;
  font-weight: 600;
}

.versus {
  flex: 0 0 auto;
  white-space: nowrap;
}

.kickoff {
  flex-shrink: 0;
  font-size: 12px;
  white-space: nowrap;
}

.market-row {
  align-items: center;
}

.market-list {
  min-height: 0;
  overflow: auto;
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
}

@media (max-width: 767px) {
  .fixture-meta {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 2px 8px !important;
  }

  .league {
    grid-column: 1;
    max-width: 100%;
  }

  .kickoff {
    grid-column: 2;
  }

  .matchup {
    grid-column: 1 / -1;
    grid-row: 2;
    width: 100%;
  }
}
</style>
