<script setup lang="ts">
import { onActivated, ref } from 'vue'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FixtureList from '@/components/FixtureList.vue'
import BetDetailsPanel from '@/views/Predictions/components/BetDetailsPanel.vue'
import CalcFixtureCard from '@/views/Predictions/components/CalcFixtureCard.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import PullToRefresh from '@/components/PullToRefresh.vue'
import { useBetCalculator } from '@/views/Predictions/composables/useBetCalculator'
import {
  officialSyncing,
  useFixturesShell,
} from '@/layouts/composables/useFixturesShell'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useScrollRestore } from '@/composables/useScrollRestore'
import { findScrollContainer } from '@/utils/scrollContainer'

defineOptions({ name: 'Predictions' })

const DESKTOP_COMPARE_ITEM_SIZE = 166

const isPhone = useIsPhone()
const listShellRef = ref<HTMLElement | null>(null)
const calcShellRef = ref<HTMLElement | null>(null)
const phoneCalcShellRef = ref<HTMLElement | null>(null)
/** Shared day expand set across desktop odds/calc columns. */
const expandedDays = ref<string[]>([])

useScrollRestore('predictions-list', listShellRef)
useScrollRestore('predictions-phone-list', phoneCalcShellRef)
const betDetailsRef = ref<InstanceType<typeof BetDetailsPanel> | null>(null)
let scrollSyncOrigin: 'odds' | 'calc' | null = null

const {
  contentLoading,
  prematchDisplayedFixtures,
  predictionsEmptyText,
  reloadPrematchDay,
  refreshOfficial,
  homeDay,
  shellTrackedIds,
} = useFixturesShell()

const { error, syncHomeListAfterDetail } = useHomeFixtures()
const { matchCount } = useBetCalculator()

const colContentStyle =
  'position: relative; min-height: 0; overflow: hidden; padding: 0;'

/** Inside desktop column cards — keep inset independent of page content padding. */
const desktopListItemsStyle = {
  paddingLeft: '10px',
  paddingRight: '10px',
  boxSizing: 'border-box',
}

function syncComparisonScroll(source: 'odds' | 'calc', event: Event) {
  if (scrollSyncOrigin && scrollSyncOrigin !== source) return
  const container = event.target as HTMLElement | null
  if (!container) return
  scrollSyncOrigin = source
  const peerShell = source === 'odds' ? calcShellRef.value : listShellRef.value
  const peer = findScrollContainer(peerShell)
  if (peer && peer !== container) peer.scrollTop = container.scrollTop
  requestAnimationFrame(() => {
    scrollSyncOrigin = null
  })
}

onActivated(() => {
  syncHomeListAfterDetail(homeDay.value, shellTrackedIds.value)
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
        <div ref="phoneCalcShellRef" class="scroll-shell">
          <PullToRefresh
            :shell="phoneCalcShellRef"
            :refreshing="officialSyncing"
            @refresh="refreshOfficial"
          />
          <FixtureList
            :fixtures="prematchDisplayedFixtures"
            :empty-description="predictionsEmptyText"
            :item-size="200"
            :padding-top="12"
            :padding-bottom="matchCount ? 16 : 20"
          >
            <template #card="{ fixture }">
              <div class="compare-slot">
                <CalcFixtureCard :fixture="fixture" />
              </div>
            </template>
          </FixtureList>
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

      <!-- 桌面：三列对照；回顶/到底放在计算器列右下角 -->
      <n-grid v-else :cols="24" :x-gap="12" class="pred-grid">
        <n-gi :span="8" class="pred-grid-item">
          <n-card
            size="small"
            :bordered="false"
            class="pred-col"
            :content-style="colContentStyle"
          >
            <template #header>
              <n-text strong>赔率 / 预测</n-text>
            </template>
            <template #header-extra>
              <n-text depth="3">{{ prematchDisplayedFixtures.length }} 场</n-text>
            </template>
            <div ref="listShellRef" class="scroll-shell">
              <PullToRefresh
                :shell="listShellRef"
                :refreshing="officialSyncing"
                @refresh="refreshOfficial"
              />
              <FixtureList
                :fixtures="prematchDisplayedFixtures"
                :empty-description="predictionsEmptyText"
                v-model:expanded-names="expandedDays"
                :item-size="DESKTOP_COMPARE_ITEM_SIZE"
                :padding-top="10"
                :padding-bottom="12"
                :items-style="desktopListItemsStyle"
                @scroll="syncComparisonScroll('odds', $event)"
              >
                <template #card="{ fixture }">
                  <div class="compare-slot">
                    <AlgorithmPredictionCard
                      :fixture="fixture"
                      standalone
                      from="predictions"
                    />
                  </div>
                </template>
              </FixtureList>
            </div>
          </n-card>
        </n-gi>

        <n-gi :span="9" class="pred-grid-item">
          <n-card
            size="small"
            :bordered="false"
            class="pred-col"
            :content-style="colContentStyle"
          >
            <template #header>
              <n-text strong>计算器</n-text>
            </template>
            <template #header-extra>
              <n-text depth="3">已选 {{ matchCount }} / 10</n-text>
            </template>
            <div ref="calcShellRef" class="scroll-shell">
              <FixtureList
                :fixtures="prematchDisplayedFixtures"
                :empty-description="predictionsEmptyText"
                v-model:expanded-names="expandedDays"
                :item-size="DESKTOP_COMPARE_ITEM_SIZE"
                :padding-top="10"
                :padding-bottom="12"
                :items-style="desktopListItemsStyle"
                @scroll="syncComparisonScroll('calc', $event)"
              >
                <template #card="{ fixture }">
                  <div class="compare-slot">
                    <CalcFixtureCard :fixture="fixture" />
                  </div>
                </template>
              </FixtureList>
              <ListBackTop
                :shell="calcShellRef"
                :sync-shell="listShellRef"
                :bottom="12"
                :right="12"
              />
            </div>
          </n-card>
        </n-gi>

        <n-gi :span="7" class="pred-grid-item">
          <n-card
            size="small"
            :bordered="false"
            class="pred-col"
            :content-style="colContentStyle"
          >
            <template #header>
              <n-text strong>投注详情</n-text>
            </template>
            <template #header-extra>
              <n-button
                size="tiny"
                type="primary"
                :disabled="!matchCount"
                @click="betDetailsRef?.openFormula()"
              >
                奖金算式
              </n-button>
            </template>
            <div class="scroll-shell">
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
  padding: 0;
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
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* 手机列表不能用 absolute inset:0，否则摘要会脱离底栏布局 */
.phone-calc > .scroll-shell {
  position: relative;
  inset: auto;
  flex: 1;
  min-height: 0;
}

.phone-calc-footer {
  flex-shrink: 0;
  z-index: 2;
  border-top: 1px solid var(--fa-border);
  background-color: var(--fa-bg-elevated);
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.18);
}

.pred-grid {
  height: 100%;
  min-height: 0;
  align-items: stretch;
}

.pred-grid-item {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
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
  padding: 10px 12px;
  flex-shrink: 0;
}

.scroll-shell {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

/* 固定槽位高度，保证左右对照卡片一致（class 写在本页 DOM 上，避免落不到子组件根） */
.compare-slot {
  height: 156px;
  overflow: hidden;
}

.compare-slot > :deep(*) {
  height: 100%;
}

@media (max-width: 767px) {
  .compare-slot {
    height: 184px;
  }
}
</style>
