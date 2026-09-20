<script setup lang="ts">
import { onActivated, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FixtureList from '@/components/FixtureList.vue'
import BetDetailsPanel from '@/views/Predictions/components/BetDetailsPanel.vue'
import CalcFixtureCard from '@/views/Predictions/components/CalcFixtureCard.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import PullToRefresh from '@/components/PullToRefresh.vue'
import { useBetCalculator } from '@/views/Predictions/composables/useBetCalculator'
import { useFixturesShell } from '@/layouts/composables/useFixturesShell'
import { useHomeFixtures, isPrematchListCacheFresh } from '@/composables/useHomeFixtures'
import { useClientDataEpoch } from '@/composables/clientDataEpoch'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useScrollRestore } from '@/composables/useScrollRestore'

defineOptions({ name: 'Predictions' })

const route = useRoute()

const isPhone = useIsPhone()
const listShellRef = ref<HTMLElement | null>(null)
const phoneCalcShellRef = ref<HTMLElement | null>(null)
/** 投注详情 Drawer 的挂载容器，使它只在列表区滑出。 */
const calcBodyRef = ref<HTMLElement | null>(null)

useScrollRestore('predictions-list', listShellRef)
useScrollRestore('predictions-phone-list', phoneCalcShellRef)

const {
  contentLoading,
  prematchDisplayedFixtures,
  predictionsEmptyText,
  reloadPrematchDay,
  homeDay,
  shellTrackedIds,
} = useFixturesShell()

const { error, syncHomeListAfterDetail } = useHomeFixtures()
const clientDataEpoch = useClientDataEpoch()
const { matchCount } = useBetCalculator()

const colContentStyle =
  'position: relative; min-height: 0; overflow: hidden; padding: 0;'

let prematchVisited = false
onActivated(() => {
  syncHomeListAfterDetail(homeDay.value, shellTrackedIds.value)
  if (
    prematchVisited &&
    !isPrematchListCacheFresh(undefined, shellTrackedIds.value)
  ) {
    void reloadPrematchDay(true)
  }
  prematchVisited = true
})

watch(clientDataEpoch, () => {
  if (route.name !== 'predictions') return
  void reloadPrematchDay(true)
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
      <div class="calc-page">
        <!-- 投注详情 Drawer 挂在这层：只盖住列表区，不占浏览器视口。 -->
        <div ref="calcBodyRef" class="calc-body">
          <!-- 手机：仅玩法列表 -->
          <div
            v-if="isPhone"
            ref="phoneCalcShellRef"
            class="scroll-shell calc-list-shell"
          >
            <PullToRefresh
              :shell="phoneCalcShellRef"
              :refreshing="contentLoading"
              @refresh="reloadPrematchDay(true)"
            />
            <FixtureList
              :fixtures="prematchDisplayedFixtures"
              :empty-description="predictionsEmptyText"
              markable
            >
              <template #card="{ fixture }">
                <div class="fixture-slot">
                  <CalcFixtureCard :fixture="fixture" />
                </div>
              </template>
            </FixtureList>
            <ListBackTop
              :shell="phoneCalcShellRef"
              :content-key="prematchDisplayedFixtures.length"
              :bottom="matchCount ? 100 : 12"
              :right="12"
            />
          </div>

          <!-- 桌面：预测与玩法占满内容区，不再为投注详情常驻留列。 -->
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
                :refreshing="contentLoading"
                @refresh="reloadPrematchDay(true)"
              />
              <FixtureList
                :fixtures="prematchDisplayedFixtures"
                :empty-description="predictionsEmptyText"
                markable
              >
                <template #card="{ fixture }">
                  <div class="fixture-row">
                    <div class="fixture-row-pred">
                      <AlgorithmPredictionCard
                        :fixture="fixture"
                        standalone
                        from="predictions"
                      />
                    </div>
                    <div class="fixture-row-calc">
                      <CalcFixtureCard :fixture="fixture" />
                    </div>
                  </div>
                </template>
              </FixtureList>
              <ListBackTop
                :shell="listShellRef"
                :content-key="prematchDisplayedFixtures.length"
                :bottom="12"
                :right="12"
              />
            </div>
          </n-card>
        </div>

        <!-- 桌面 / 手机共用：有选择才出现，展开后用底部 Drawer 承载详情。 -->
        <div v-if="matchCount" class="calc-footer">
          <BetDetailsPanel :drawer-target="calcBodyRef" />
        </div>
      </div>
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

.calc-page {
  /* 摘要条与投注详情 Drawer 共用这个宽度，两者左边缘和右边缘才对得齐。 */
  --calc-panel-width: 400px;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* Drawer 以这层为定位父级：position 必须是 relative，否则会退回视口。 */
.calc-body {
  position: relative;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* 列表不能用 absolute inset:0，否则摘要会脱离底部布局。 */
.calc-body > .calc-list-shell {
  position: relative;
  inset: auto;
  flex: 1;
  min-height: 0;
}

/* 工具条背景铺满内容区，内部控件由 BetDetailsPanel 限宽并靠左。 */
.calc-footer {
  align-self: stretch;
  width: 100%;
  flex-shrink: 0;
  z-index: 2;
  background-color: var(--fa-bg-elevated);
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.22);
}

/* 手机通栏：摘要与 Drawer 都铺满内容区。 */
.predictions-page.phone .calc-page {
  --calc-panel-width: 100%;
}

.predictions-page.phone .calc-footer {
  align-self: stretch;
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
