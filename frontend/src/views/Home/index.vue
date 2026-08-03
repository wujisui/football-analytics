<script setup lang="ts">
import { computed, onActivated, ref } from 'vue'

import FixtureList from '@/components/FixtureList.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import { useFixturesShell } from '@/layouts/composables/useFixturesShell'
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
    <n-scrollbar
      class="fa-page-list-scroll"
      trigger="hover"
      content-class="fa-page-content-padding"
    >
      <n-alert v-if="error" type="error" title="获取失败" class="fa-page-list-state">
        <n-space align="center" :size="12">
          <span>{{ error }}</span>
          <n-button size="small" type="primary" @click="reloadPrematchDay(true)">重试</n-button>
        </n-space>
      </n-alert>

      <n-spin v-else :show="contentLoading">
        <div class="fa-page-list-body">
          <FixtureList
            mode="full"
            :fixtures="fixtures"
            :empty-description="homeEmptyText"
            :group-by-day="true"
          />
        </div>
      </n-spin>
    </n-scrollbar>
    <ListBackTop :shell="listShellRef" />
  </div>
</template>
