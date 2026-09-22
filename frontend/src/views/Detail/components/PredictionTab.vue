<script setup lang="ts">
import { computed } from 'vue'

import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import PredictionResult from '@/views/Detail/components/PredictionResult.vue'
import type { FixtureResponse, OddsPackage } from '@/api/types'
import { formatLocalMonthDayMinute } from '@/utils/format'
import { useAuthSession } from '@/composables/useAuthSession'
import { hasOddsMarkets } from '@/utils/oddsDisplay'

const props = defineProps<{
  fixture: FixtureResponse
  oddsRefreshing?: boolean
  oddsRefreshBlocked?: boolean
  officialSyncBusy?: boolean
}>()
const emit = defineEmits<{ 'refresh-odds': [] }>()
const { isAdmin } = useAuthSession()

interface OddsStage {
  key: 'initial' | 'mid' | 'late' | 'current'
  title: string
  description?: string
  odds: OddsPackage
  capturedAt: string
}

const oddsStages = computed<OddsStage[]>(() => {
  const pkg = props.fixture.analysis.package
  const candidates = [
    {
      key: 'initial' as const,
      title: '初盘',
      description: '首次采集的机构盘口',
      odds: pkg?.odds_opening,
    },
    {
      key: 'mid' as const,
      title: '中盘',
      odds: pkg?.odds_mid,
    },
    {
      key: 'late' as const,
      title: '临场',
      odds: pkg?.odds_late,
    },
    {
      key: 'current' as const,
      title: '即时盘',
      odds: pkg?.odds,
    },
  ].filter(
    (stage): stage is Omit<OddsStage, 'capturedAt'> =>
      !!stage.odds && hasOddsMarkets(stage.odds),
  )

  // 同一次采集可能同时命中一个目标槽位和 current，只展示语义更靠后的阶段。
  const seen = new Set<string>()
  return candidates
    .reverse()
    .filter((stage) => {
      const capturedAt = stage.odds.scraped_at || stage.odds.captured_at || ''
      const identity = capturedAt || `${stage.key}-without-clock`
      if (seen.has(identity)) return false
      seen.add(identity)
      return true
    })
    .reverse()
    .map(stage => ({
      ...stage,
      capturedAt: stage.odds.scraped_at || stage.odds.captured_at || '',
    }))
})
const showAnyBoard = computed(() => oddsStages.value.length > 0)

const isFinished = computed(
  () => (props.fixture.status ?? '').toLowerCase() === 'finished',
)
const canRefreshOdds = computed(
  () =>
    isAdmin.value
    && props.fixture.odds_refresh_allowed === true,
)
</script>

<template>
  <div class="prediction-tab">
    <template v-if="showAnyBoard">
      <section
        v-for="stage in oddsStages"
        :key="stage.key"
        class="fa-section"
      >
        <div class="board-head">
          <div class="board-title">
            <h3 class="fa-section-title">{{ stage.title }}</h3>
            <n-text v-if="stage.description" depth="3" class="board-description">
              {{ stage.description }}
            </n-text>
          </div>
          <n-flex align="center" :size="8">
            <n-text v-if="stage.capturedAt" depth="3" class="board-time">
              {{ formatLocalMonthDayMinute(stage.capturedAt) }}
            </n-text>
            <n-button
              v-if="canRefreshOdds && stage.key === 'current'"
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
        </div>
        <PreMatchOddsTable :odds="stage.odds" />
      </section>
    </template>

    <section v-else-if="canRefreshOdds" class="fa-section">
      <div class="board-head">
        <h3 class="fa-section-title">盘口</h3>
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
      </div>
      <n-empty description="暂无官方盘口，可手动更新本场" />
    </section>

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
      :analyzed-at="formatLocalMonthDayMinute(fixture.analysis.analyzed_at)"
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

.board-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.board-title {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px 10px;
  min-width: 0;
}

.board-description,
.board-time {
  font-size: 12px;
}
</style>
