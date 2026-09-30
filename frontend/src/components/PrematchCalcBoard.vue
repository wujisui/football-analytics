<script setup lang="ts">
import { ref } from 'vue'

import type { FixtureResponse } from '@/api/types'
import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FixtureList from '@/components/FixtureList.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import PullToRefresh from '@/components/PullToRefresh.vue'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useScrollRestore } from '@/composables/useScrollRestore'
import type { DetailFrom } from '@/utils/detailNav'
import BetDetailsPanel from '@/views/Predictions/components/BetDetailsPanel.vue'
import CalcFixtureCard from '@/views/Predictions/components/CalcFixtureCard.vue'
import { useBetCalculator } from '@/views/Predictions/composables/useBetCalculator'

const props = withDefaults(
  defineProps<{
    fixtures: FixtureResponse[]
    emptyDescription: string
    refreshing?: boolean
    from?: DetailFrom
    date?: string | null
    /** 比赛页跨两天时按赛程日分组；赛程页已经选定一天，不再套日期头。 */
    groupByDay?: boolean
    /** Scroll-restore bucket; 比赛 and 赛程未来日各记一份。 */
    scrollKey: string
  }>(),
  {
    refreshing: false,
    from: 'predictions',
    date: null,
    groupByDay: true,
  },
)

const emit = defineEmits<{
  refresh: []
}>()

const isPhone = useIsPhone()
const listShellRef = ref<HTMLElement | null>(null)
const phoneListShellRef = ref<HTMLElement | null>(null)
const calcBodyRef = ref<HTMLElement | null>(null)

useScrollRestore(`${props.scrollKey}-list`, listShellRef)
useScrollRestore(`${props.scrollKey}-phone-list`, phoneListShellRef)

const { matchCount } = useBetCalculator()

const colContentStyle =
  'position: relative; min-height: 0; overflow: hidden; padding: 0;'
</script>

<template>
  <div class="calc-page" :class="{ phone: isPhone }">
    <div ref="calcBodyRef" class="calc-body">
      <div
        v-if="isPhone"
        ref="phoneListShellRef"
        class="scroll-shell calc-list-shell"
      >
        <PullToRefresh
          :shell="phoneListShellRef"
          :refreshing="refreshing"
          @refresh="emit('refresh')"
        />
        <FixtureList
          :fixtures="fixtures"
          :empty-description="emptyDescription"
          :group-by-day="groupByDay"
          :date="date"
          :from="from"
          markable
        >
          <template #card="{ fixture }">
            <div class="fixture-slot">
              <CalcFixtureCard :fixture="fixture" :from="from" />
            </div>
          </template>
        </FixtureList>
        <ListBackTop
          :shell="phoneListShellRef"
          :content-key="fixtures.length"
          :bottom="matchCount ? 100 : 12"
          :right="12"
        />
      </div>

      <n-card
        v-else
        size="small"
        :bordered="false"
        class="pred-col"
        :content-style="colContentStyle"
      >
        <div ref="listShellRef" class="scroll-shell">
          <PullToRefresh
            :shell="listShellRef"
            :refreshing="refreshing"
            @refresh="emit('refresh')"
          />
          <FixtureList
            :fixtures="fixtures"
            :empty-description="emptyDescription"
            :group-by-day="groupByDay"
            :date="date"
            :from="from"
            markable
          >
            <template #card="{ fixture }">
              <div class="fixture-row">
                <div class="fixture-row-pred">
                  <AlgorithmPredictionCard
                    :fixture="fixture"
                    standalone
                    :from="from"
                  />
                </div>
                <div class="fixture-row-calc">
                  <CalcFixtureCard :fixture="fixture" :from="from" />
                </div>
              </div>
            </template>
          </FixtureList>
          <ListBackTop
            :shell="listShellRef"
            :content-key="fixtures.length"
            :bottom="12"
            :right="12"
          />
        </div>
      </n-card>
    </div>

    <div v-if="matchCount" class="calc-footer">
      <BetDetailsPanel :drawer-target="calcBodyRef" />
    </div>
  </div>
</template>

<style scoped>
.calc-page {
  --calc-panel-width: 400px;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.calc-page.phone {
  --calc-panel-width: 100%;
}

.calc-body {
  position: relative;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.calc-body > .calc-list-shell {
  position: relative;
  inset: auto;
  flex: 1;
  min-height: 0;
}

.calc-footer {
  align-self: stretch;
  width: 100%;
  flex-shrink: 0;
  z-index: 2;
  background-color: var(--fa-bg-elevated);
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.22);
}

.pred-col {
  flex: 1;
  width: 100%;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.pred-col :deep(.n-card-header) {
  padding: 10px 12px 0;
  flex-shrink: 0;
}

.scroll-shell {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.fixture-slot {
  height: 184px;
  overflow: hidden;
}

.fixture-slot > :deep(*) {
  height: 100%;
}

.fixture-row {
  display: grid;
  grid-template-columns: minmax(0, 5.5fr) minmax(0, 4.5fr);
  gap: 5px;
  height: 147px;
  min-width: 0;
  overflow: hidden;
}

.fixture-row-pred,
.fixture-row-calc {
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.fixture-row-pred > :deep(*),
.fixture-row-calc > :deep(*) {
  height: 100%;
}
</style>
