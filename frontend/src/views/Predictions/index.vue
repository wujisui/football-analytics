<script setup lang="ts">
import { onActivated, watch } from 'vue'
import { useRoute } from 'vue-router'

import PrematchCalcBoard from '@/components/PrematchCalcBoard.vue'
import { useFixturesShell } from '@/layouts/composables/useFixturesShell'
import { useHomeFixtures, isPrematchListCacheFresh } from '@/composables/useHomeFixtures'
import { useClientDataEpoch } from '@/composables/clientDataEpoch'
import { useIsPhone } from '@/composables/useMediaQuery'

defineOptions({ name: 'Predictions' })

const route = useRoute()
const isPhone = useIsPhone()

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
      <PrematchCalcBoard
        :fixtures="prematchDisplayedFixtures"
        :empty-description="predictionsEmptyText"
        :refreshing="contentLoading"
        :date="homeDay"
        scroll-key="predictions"
        from="predictions"
        @refresh="reloadPrematchDay(true)"
      />
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
</style>
