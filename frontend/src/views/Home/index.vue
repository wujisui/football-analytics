<script setup lang="ts">
import { computed, onActivated, ref } from 'vue'

import FixtureList from '@/components/FixtureList.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import PullToRefresh from '@/components/PullToRefresh.vue'
import {
  officialSyncing,
  useFixturesShell,
} from '@/layouts/composables/useFixturesShell'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import { useScrollRestore } from '@/composables/useScrollRestore'

defineOptions({ name: 'Home' })

const listShellRef = ref<HTMLElement | null>(null)

useScrollRestore('home-list', listShellRef)

const {
  contentLoading,
  prematchDisplayedFixtures,
  homeEmptyText,
  reloadPrematchDay,
  refreshOfficial,
  homeDay,
  shellTrackedIds,
} = useFixturesShell()

const { error, syncHomeListAfterDetail } = useHomeFixtures()

const fixtures = computed(() => prematchDisplayedFixtures.value)

onActivated(() => {
  syncHomeListAfterDetail(homeDay.value, shellTrackedIds.value)
})
</script>

<template>
  <div ref="listShellRef" class="fa-page-list-shell">
    <PullToRefresh
      :shell="listShellRef"
      :refreshing="officialSyncing"
      @refresh="refreshOfficial"
    />
    <n-alert v-if="error" type="error" title="获取失败" class="home-alert">
      <n-space align="center" :size="12">
        <span>{{ error }}</span>
        <n-button size="small" type="primary" @click="reloadPrematchDay(true)">重试</n-button>
      </n-space>
    </n-alert>
    <n-spin v-else :show="contentLoading" class="home-spin">
      <FixtureList
        mode="full"
        :fixtures="fixtures"
        :empty-description="homeEmptyText"
        :group-by-day="true"
        :padding-top="12"
        :padding-bottom="20"
      />
    </n-spin>
    <ListBackTop :shell="listShellRef" />
  </div>
</template>

<style scoped>
.home-alert {
  flex-shrink: 0;
  margin: 12px var(--fa-content-inline) 0;
}

.home-spin {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.home-spin :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}
</style>
