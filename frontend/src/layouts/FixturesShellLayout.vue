<script setup lang="ts">
import { onActivated, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import HomeDateStrip from '@/components/HomeDateStrip.vue'
import LeagueFilterTrigger from '@/components/LeagueFilterTrigger.vue'
import LeagueMenu from '@/components/LeagueMenu.vue'
import PageToolbarSearch from '@/components/PageToolbarSearch.vue'
import {
  activateFixturesShell,
  initFixturesShellOnMount,
  useFixturesShell,
} from '@/composables/useFixturesShell'
import { useIsPhone } from '@/composables/useMediaQuery'

defineOptions({ name: 'FixturesShellLayout' })

const route = useRoute()
const isPhone = useIsPhone()

const {
  selectedDay,
  selectedLeagueId,
  teamSearch,
  siderCollapsed,
  leagueDrawerShow,
  shellLoading,
  shellTrackedIds,
  shellFilterOptions,
  shellFilterActive,
  shellMenuLeagues,
  shellCountByLeague,
  shellTotalCount,
  breadcrumbRoot,
  breadcrumbFilter,
  dayCountLabel,
  filterConfirming,
  confirmFilter,
  selectLeague,
  reloadPrematchDay,
  isResultsPage,
  isScheduleFutureDay,
} = useFixturesShell()

watch(selectedDay, () => {
  if (isResultsPage.value) return
  void reloadPrematchDay()
})

onMounted(() => {
  initFixturesShellOnMount(route.name === 'results')
})

onActivated(() => {
  activateFixturesShell()
})
</script>

<template>
  <div class="fa-page-frame">
    <n-layout
      :has-sider="!isPhone"
      class="shell-layout fa-page-shell"
      content-style="height: 100%;"
    >
      <n-layout-sider
        v-if="!isPhone"
        v-model:collapsed="siderCollapsed"
        bordered
        collapse-mode="width"
        :collapsed-width="64"
        :width="232"
        :native-scrollbar="false"
        show-trigger="bar"
        content-style="height: 100%;"
      >
        <LeagueMenu
          :leagues="shellMenuLeagues"
          :selected-league-id="selectedLeagueId"
          :pending-count-by-league="shellCountByLeague"
          :total-pending="shellTotalCount"
          :loading="shellLoading"
          :collapsed="siderCollapsed"
          @select="selectLeague"
        >
          <template #filter>
            <LeagueFilterTrigger
              :options="shellFilterOptions"
              :tracked-ids="shellTrackedIds"
              :icon-only="siderCollapsed"
              :filter-active="shellFilterActive"
              :confirming="filterConfirming"
              :finished-mode="isResultsPage && !isScheduleFutureDay"
              @confirm="confirmFilter"
            />
          </template>
        </LeagueMenu>
      </n-layout-sider>

      <n-layout
        class="shell-main"
        style="height: 100%; flex: 1; min-height: 0; min-width: 0;"
        content-style="display: flex; flex-direction: column; height: 100%; overflow: hidden;"
      >
        <n-layout-header bordered class="fa-page-toolbar" style="flex-shrink: 0;">
          <div class="fa-toolbar-top">
            <n-button
              v-if="isPhone"
              size="small"
              secondary
              class="league-trigger"
              @click="leagueDrawerShow = true"
            >
              联赛
            </n-button>
            <n-breadcrumb class="fa-toolbar-crumb">
              <n-breadcrumb-item @click="selectLeague(null)">
                {{ breadcrumbRoot }}
              </n-breadcrumb-item>
              <n-breadcrumb-item>{{ breadcrumbFilter }}</n-breadcrumb-item>
            </n-breadcrumb>
          </div>

          <HomeDateStrip
            v-if="isResultsPage"
            v-model="selectedDay"
          />

          <div class="shell-list-meta">
            <span class="day-stat">{{ dayCountLabel }}</span>
            <PageToolbarSearch v-model="teamSearch" />
          </div>
        </n-layout-header>

        <div class="shell-content">
          <router-view v-slot="{ Component }">
            <keep-alive :include="['Home', 'Predictions', 'Results']">
              <component :is="Component" />
            </keep-alive>
          </router-view>
        </div>
      </n-layout>
    </n-layout>

    <n-drawer
      v-if="isPhone"
      v-model:show="leagueDrawerShow"
      placement="left"
      width="88%"
      to="body"
      display-directive="show"
      class="league-drawer"
    >
      <n-drawer-content
        title="联赛"
        closable
        :native-scrollbar="false"
        body-content-style="padding: 0; height: 100%; display: flex; flex-direction: column;"
      >
        <LeagueMenu
          :leagues="shellMenuLeagues"
          :selected-league-id="selectedLeagueId"
          :pending-count-by-league="shellCountByLeague"
          :total-pending="shellTotalCount"
          :loading="shellLoading"
          :collapsed="false"
          @select="selectLeague"
        >
          <template #filter>
            <LeagueFilterTrigger
              drawer-mode
              :options="shellFilterOptions"
              :tracked-ids="shellTrackedIds"
              :filter-active="shellFilterActive"
              :confirming="filterConfirming"
              :finished-mode="isResultsPage && !isScheduleFutureDay"
              @confirm="confirmFilter"
            />
          </template>
        </LeagueMenu>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.shell-layout {
  height: 100%;
  overflow: hidden;
  background: var(--fa-bg);
}

.shell-main {
  background: var(--fa-bg);
  min-width: 0;
  overflow: hidden;
}

.league-trigger {
  flex-shrink: 0;
}

:deep(.league-drawer .n-drawer-body-content-wrapper) {
  height: 100%;
}

:deep(.league-drawer .league-menu) {
  height: 100%;
}

.shell-list-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 0 4px;
}

.day-stat {
  font-size: 13px;
  color: var(--fa-text-secondary);
  white-space: nowrap;
}

.shell-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--fa-bg);
}

.shell-content :deep(> *) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

:deep(.n-breadcrumb-item:first-child .n-breadcrumb-item__link) {
  cursor: pointer;
}
</style>
