<script setup lang="ts">
import { computed } from 'vue'

import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import PredictionResult from '@/views/Detail/components/PredictionResult.vue'
import type { FixtureResponse } from '@/api/types'
import { formatDateTime, hasKickedOff } from '@/utils/format'
import { useAuthSession } from '@/composables/useAuthSession'
import { hasOddsMarkets, isOpeningDistinct } from '@/utils/oddsDisplay'

const props = defineProps<{
  fixture: FixtureResponse
  oddsRefreshing?: boolean
  oddsRefreshBlocked?: boolean
  officialSyncBusy?: boolean
}>()
const emit = defineEmits<{ 'refresh-odds': [] }>()
const { isAdmin } = useAuthSession()

const oddsCurrent = computed(() => props.fixture.analysis.package?.odds ?? null)
const oddsOpening = computed(() => props.fixture.analysis.package?.odds_opening ?? null)

const showCurrent = computed(() => hasOddsMarkets(oddsCurrent.value))
/** Same capture time = 初盘 was just frozen from this board; show it as 即时盘 only. */
const showOpening = computed(() =>
  isOpeningDistinct(oddsOpening.value, oddsCurrent.value),
)
const showAnyBoard = computed(() => showCurrent.value || showOpening.value)

const isFinished = computed(
  () => (props.fixture.status ?? '').toLowerCase() === 'finished',
)
const canRefreshOdds = computed(
  () =>
    isAdmin.value
    && (props.fixture.status ?? '').toLowerCase() === 'pending'
    && !hasKickedOff(props.fixture.fixture_date),
)
</script>

<template>
  <div class="prediction-tab">
    <template v-if="showAnyBoard">
      <n-card
        v-if="showCurrent"
        size="small"
        title="即时盘"
        style="background: var(--fa-bg-elevated);"
      >
        <template #header-extra>
          <n-flex align="center" :size="8">
            <n-text v-if="oddsCurrent?.captured_at" depth="3" style="font-size: 12px;">
              {{ formatDateTime(oddsCurrent.captured_at) }}
            </n-text>
            <n-button
              v-if="canRefreshOdds"
              size="tiny"
              secondary
              type="primary"
              :loading="oddsRefreshing"
              :disabled="oddsRefreshBlocked"
              @click="emit('refresh-odds')"
            >
              更新盘口
            </n-button>
          </n-flex>
        </template>
        <PreMatchOddsTable :odds="oddsCurrent" />
      </n-card>

      <n-card
        v-if="showOpening"
        size="small"
        title="初盘"
        style="background: var(--fa-bg-elevated);"
      >
        <template #header-extra>
          <n-flex align="center" :size="8">
            <n-text v-if="oddsOpening?.captured_at" depth="3" style="font-size: 12px;">
              {{ formatDateTime(oddsOpening.captured_at) }}
            </n-text>
            <n-button
              v-if="canRefreshOdds && !showCurrent"
              size="tiny"
              secondary
              type="primary"
              :loading="oddsRefreshing"
              :disabled="oddsRefreshBlocked"
              @click="emit('refresh-odds')"
            >
              更新盘口
            </n-button>
          </n-flex>
        </template>
        <PreMatchOddsTable :odds="oddsOpening" />
      </n-card>
    </template>

    <n-card
      v-else-if="canRefreshOdds"
      size="small"
      title="盘口"
      style="background: var(--fa-bg-elevated);"
    >
      <template #header-extra>
        <n-button
          size="tiny"
          secondary
          type="primary"
          :loading="oddsRefreshing"
          :disabled="oddsRefreshBlocked"
          @click="emit('refresh-odds')"
        >
          更新盘口
        </n-button>
      </template>
      <n-empty description="暂无官方盘口，可手动更新本场" />
    </n-card>

    <n-alert
      v-if="canRefreshOdds && officialSyncBusy"
      type="warning"
      :bordered="false"
    >
      后台官方同步正在执行，暂时不能单独更新本场盘口
    </n-alert>

    <PredictionResult
      :fixture="fixture"
      :is-finished="isFinished"
      :data-source="fixture.analysis.data_source"
      :analyzed-at="formatDateTime(fixture.analysis.analyzed_at)"
      :handicap-market-note="fixture.analysis.handicap_market_note || ''"
    />
  </div>
</template>

<style scoped>
.prediction-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
