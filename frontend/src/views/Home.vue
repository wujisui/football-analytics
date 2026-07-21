<script setup lang="ts">
import { onActivated, ref } from 'vue'

import FixtureList from '@/components/FixtureList.vue'
import ListBackTop from '@/components/ListBackTop.vue'
import { useFixturesShell } from '@/composables/useFixturesShell'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import { useIsPhone } from '@/composables/useMediaQuery'

defineOptions({ name: 'Home' })

const isPhone = useIsPhone()
const listShellRef = ref<HTMLElement | null>(null)

const {
  contentLoading,
  homeDisplayedFixtures,
  homeEmptyText,
  forceRefreshDay,
  homeDay,
} = useFixturesShell()

const { error, syncHomeListAfterDetail } = useHomeFixtures()

onActivated(() => {
  syncHomeListAfterDetail(homeDay.value)
})
</script>

<template>
  <div ref="listShellRef" class="page-list-shell">
    <n-scrollbar
      class="page-list-scroll"
      trigger="hover"
      :content-style="
        isPhone
          ? 'padding: 12px 12px 20px; box-sizing: border-box;'
          : 'padding: 16px 20px 24px; box-sizing: border-box;'
      "
    >
      <n-alert v-if="error" type="error" title="获取失败" class="state">
        <n-space align="center" :size="12">
          <span>{{ error }}</span>
          <n-button size="small" type="primary" @click="forceRefreshDay()">重试</n-button>
        </n-space>
      </n-alert>

      <n-spin v-else :show="contentLoading">
        <div class="spin-body">
          <FixtureList
            :fixtures="homeDisplayedFixtures"
            :empty-description="homeEmptyText"
            :group-by-day="false"
          />
        </div>
      </n-spin>
    </n-scrollbar>
    <ListBackTop :shell="listShellRef" />
  </div>
</template>

<style scoped>
.page-list-shell {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.page-list-scroll {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.spin-body {
  min-height: 200px;
}

.state {
  margin-bottom: 12px;
}
</style>
