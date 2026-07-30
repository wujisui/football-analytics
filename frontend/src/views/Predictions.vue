<script setup lang="ts">
import type { ScrollbarInst } from 'naive-ui'
import { onActivated, ref } from 'vue'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import BetDetailsPanel from '@/components/calculator/BetDetailsPanel.vue'
import CalcFixtureCard from '@/components/calculator/CalcFixtureCard.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import { useBetCalculator } from '@/composables/useBetCalculator'
import { useFixturesShell } from '@/composables/useFixturesShell'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import { useIsPhone } from '@/composables/useMediaQuery'

defineOptions({ name: 'Predictions' })

const isPhone = useIsPhone()
const listShellRef = ref<HTMLElement | null>(null)
const calcShellRef = ref<HTMLElement | null>(null)
const phoneCalcShellRef = ref<HTMLElement | null>(null)
const oddsScrollbarRef = ref<ScrollbarInst | null>(null)
const calcScrollbarRef = ref<ScrollbarInst | null>(null)
const betDetailsRef = ref<InstanceType<typeof BetDetailsPanel> | null>(null)
let scrollSyncOrigin: 'odds' | 'calc' | null = null

const {
  contentLoading,
  prematchDisplayedFixtures,
  predictionsEmptyText,
  reloadPrematchDay,
  homeDay,
} = useFixturesShell()

const { error, syncHomeListAfterDetail } = useHomeFixtures()
const { matchCount } = useBetCalculator()

function syncComparisonScroll(source: 'odds' | 'calc', event: Event) {
  if (scrollSyncOrigin && scrollSyncOrigin !== source) return

  const container = event.target as HTMLElement | null
  if (!container) return

  scrollSyncOrigin = source
  const peer =
    source === 'odds' ? calcScrollbarRef.value : oddsScrollbarRef.value
  peer?.scrollTo({ top: container.scrollTop })
  requestAnimationFrame(() => {
    scrollSyncOrigin = null
  })
}

onActivated(() => {
  syncHomeListAfterDetail(homeDay.value)
})
</script>

<template>
  <div class="predictions-page" :class="{ phone: isPhone }">
    <n-alert v-if="error" type="error" title="获取失败" class="page-alert">
      <n-space align="center" :size="12">
        <n-text>{{ error }}</n-text>
        <n-button size="small" type="primary" @click="reloadPrematchDay(true)">
          重试
        </n-button>
      </n-space>
    </n-alert>

    <n-spin v-else :show="contentLoading" class="page-spin">
      <!-- 手机：计算器列表 + 选中后底部摘要 -->
      <div v-if="isPhone" class="phone-calc">
        <div ref="phoneCalcShellRef" class="phone-calc-scroll">
          <n-scrollbar style="height: 100%;" trigger="hover">
            <div class="col-body">
              <n-empty
                v-if="!prematchDisplayedFixtures.length"
                :description="predictionsEmptyText"
                size="small"
              />
              <n-space v-else vertical :size="10">
                <CalcFixtureCard
                  v-for="fixture in prematchDisplayedFixtures"
                  :key="`phone-calc-${fixture.fixture_id}`"
                  :fixture="fixture"
                  class="compare-card"
                />
              </n-space>
            </div>
          </n-scrollbar>
          <ListBackTop
            :shell="phoneCalcShellRef"
            :bottom="matchCount ? 120 : 12"
            :right="12"
          />
        </div>

        <div v-if="matchCount" class="phone-calc-footer">
          <BetDetailsPanel footer-only />
        </div>
      </div>

      <!-- 桌面：三列对照 -->
      <n-grid v-else :cols="24" :x-gap="12" class="pred-grid">
        <n-gi :span="8" class="pred-grid-item">
          <n-card
            size="small"
            class="pred-col"
            content-style="position: relative; min-height: 0; overflow: hidden; padding: 0;"
          >
            <template #header>
              <n-text strong>赔率 / 预测</n-text>
            </template>
            <template #header-extra>
              <n-text depth="3">{{ prematchDisplayedFixtures.length }} 场</n-text>
            </template>
            <div ref="listShellRef" class="col-scroll-shell">
              <n-scrollbar
                ref="oddsScrollbarRef"
                style="height: 100%;"
                trigger="hover"
                @scroll="syncComparisonScroll('odds', $event)"
              >
                <div class="col-body">
                  <n-empty
                    v-if="!prematchDisplayedFixtures.length"
                    :description="predictionsEmptyText"
                    size="small"
                  />
                  <n-space v-else vertical :size="10">
                    <AlgorithmPredictionCard
                      v-for="fixture in prematchDisplayedFixtures"
                      :key="`odds-${fixture.fixture_id}`"
                      :fixture="fixture"
                      standalone
                      compact
                      from="predictions"
                      class="compare-card"
                    />
                  </n-space>
                </div>
              </n-scrollbar>
              <ListBackTop :shell="listShellRef" :bottom="12" :right="12" />
            </div>
          </n-card>
        </n-gi>

        <n-gi :span="9" class="pred-grid-item">
          <n-card
            size="small"
            class="pred-col"
            content-style="position: relative; min-height: 0; overflow: hidden; padding: 0;"
          >
            <template #header>
              <n-text strong>计算器</n-text>
            </template>
            <template #header-extra>
              <n-text depth="3">已选 {{ matchCount }} / 10</n-text>
            </template>
            <div ref="calcShellRef" class="col-scroll-shell">
              <n-scrollbar
                ref="calcScrollbarRef"
                style="height: 100%;"
                trigger="hover"
                @scroll="syncComparisonScroll('calc', $event)"
              >
                <div class="col-body">
                  <n-empty
                    v-if="!prematchDisplayedFixtures.length"
                    :description="predictionsEmptyText"
                    size="small"
                  />
                  <n-space v-else vertical :size="10">
                    <CalcFixtureCard
                      v-for="fixture in prematchDisplayedFixtures"
                      :key="`calc-${fixture.fixture_id}`"
                      :fixture="fixture"
                      class="compare-card"
                    />
                  </n-space>
                </div>
              </n-scrollbar>
              <ListBackTop :shell="calcShellRef" :bottom="12" :right="12" />
            </div>
          </n-card>
        </n-gi>

        <n-gi :span="7" class="pred-grid-item">
          <n-card
            size="small"
            class="pred-col"
            content-style="position: relative; min-height: 0; overflow: hidden; padding: 0;"
          >
            <template #header>
              <n-text strong>投注详情</n-text>
            </template>
            <template #header-extra>
              <n-button
                size="tiny"
                secondary
                :disabled="!matchCount"
                @click="betDetailsRef?.openFormula()"
              >
                奖金算式
              </n-button>
            </template>
            <div class="col-scroll-shell prize-shell">
              <BetDetailsPanel ref="betDetailsRef" />
            </div>
          </n-card>
        </n-gi>
      </n-grid>
    </n-spin>
  </div>
</template>

<style scoped>
.predictions-page {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  height: 100%;
  padding: var(--fa-content-block-start) var(--fa-content-inline);
  box-sizing: border-box;
  overflow: hidden;
}

.predictions-page.phone {
  padding-inline: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.page-alert {
  flex-shrink: 0;
  margin-bottom: 10px;
}

.page-spin {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.page-spin :deep(.n-spin-container),
.page-spin :deep(.n-spin-content) {
  height: 100%;
  min-height: 0;
}

.phone-calc {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.phone-calc-scroll {
  position: relative;
  min-height: 0;
  overflow: hidden;
}

.phone-calc-footer {
  flex-shrink: 0;
  border-top: 1px solid var(--fa-border);
  background: var(--fa-bg-elevated);
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.12);
}

.pred-grid {
  height: 100%;
  min-height: 0;
}

.pred-grid-item {
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.pred-col {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.pred-col :deep(.n-card-header) {
  padding: 10px 12px;
  flex-shrink: 0;
}

.col-scroll-shell {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.col-body {
  padding: 10px;
}

.compare-card {
  height: 156px;
  overflow: hidden;
}

.prize-shell {
  position: absolute;
  inset: 0;
}

@media (max-width: 767px) {
  .compare-card {
    height: 184px;
  }
}
</style>
