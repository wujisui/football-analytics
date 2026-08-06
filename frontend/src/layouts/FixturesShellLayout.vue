<script setup lang="ts">
import { FilterOutline } from '@vicons/ionicons5'
import { computed, onActivated, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import HomeDateStrip from '@/layouts/components/HomeDateStrip.vue'
import LeagueFilterTrigger from '@/layouts/components/LeagueFilterTrigger.vue'
import LeagueMenu from '@/layouts/components/LeagueMenu.vue'
import ShellBreadcrumb from '@/layouts/components/ShellBreadcrumb.vue'
import PageToolbarSearch from '@/components/PageToolbarSearch.vue'
import {
  bootstrapFixturesShell,
  useFixturesShell,
} from '@/layouts/composables/useFixturesShell'
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
  contentLoading,
  shellTrackedIds,
  shellFilterOptions,
  shellFilterActive,
  shellMenuLeagues,
  shellCountByLeague,
  shellTotalCount,
  breadcrumbRoot,
  breadcrumbFilter,
  dayCountLabel,
  confirmFilter,
  selectLeague,
  isResultsPage,
  isScheduleFutureDay,
} = useFixturesShell()

/** Results past/today: date strip only. Future schedule day: same league chrome as calculator. */
const showShellLeagueNav = computed(
  () => !isResultsPage.value || isScheduleFutureDay.value,
)

onMounted(() => {
  bootstrapFixturesShell({ reloadPrematch: route.name !== 'results' })
})

onActivated(() => {
  bootstrapFixturesShell()
})
</script>

<template>
  <div class="fa-page-frame">
    <n-layout
      :has-sider="!isPhone && showShellLeagueNav"
      class="shell-layout fa-page-shell"
      content-style="height: 100%;"
    >
      <n-layout-sider
        v-if="!isPhone && showShellLeagueNav"
        v-model:collapsed="siderCollapsed"
        class="league-sider"
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
          :count-by-league="shellCountByLeague"
          :total-count="shellTotalCount"
          :loading="contentLoading"
          :collapsed="siderCollapsed"
          @select="selectLeague"
        >
          <template #filter>
            <LeagueFilterTrigger
              :options="shellFilterOptions"
              :tracked-ids="shellTrackedIds"
              :icon-only="siderCollapsed"
              :filter-active="shellFilterActive"
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
        <n-layout-header
          v-if="isPhone || showShellLeagueNav"
          class="fa-page-toolbar"
          style="flex-shrink: 0;"
        >
          <!-- 赛果日：仅日期条 -->
          <HomeDateStrip
            v-if="isResultsPage && !isScheduleFutureDay"
            v-model="selectedDay"
          />

          <!-- 未来赛程 · PC：面包屑与日期同一行 -->
          <div
            v-else-if="isResultsPage && isScheduleFutureDay && !isPhone"
            class="results-future-header"
          >
            <ShellBreadcrumb
              :root-label="breadcrumbRoot"
              :filter-label="breadcrumbFilter"
              @select-root="selectLeague(null)"
            />
            <HomeDateStrip v-model="selectedDay" class="results-future-dates" />
          </div>

          <!-- 未来赛程 · 手机：日期条在上，联赛行在下 -->
          <HomeDateStrip
            v-else-if="isResultsPage && isScheduleFutureDay && isPhone"
            v-model="selectedDay"
          />

          <!-- 计算器 / 赛程·未来(手机联赛行) -->
          <div
            v-if="!isResultsPage || (isScheduleFutureDay && isPhone)"
            class="fa-toolbar-top"
          >
            <n-button
              v-if="isPhone"
              size="small"
              secondary
              type="tertiary"
              class="league-trigger"
              @click="leagueDrawerShow = true"
            >
              <template #icon>
                <n-icon :component="FilterOutline" />
              </template>
              联赛
            </n-button>
            <ShellBreadcrumb
              v-if="!isPhone"
              :root-label="breadcrumbRoot"
              :filter-label="breadcrumbFilter"
              @select-root="selectLeague(null)"
            />

            <template v-if="isPhone">
              <span class="fa-toolbar-day-stat">{{ dayCountLabel }}</span>
              <div class="fa-toolbar-end">
                <PageToolbarSearch v-model="teamSearch" />
              </div>
            </template>
          </div>

          <div
            v-if="!isPhone && showShellLeagueNav"
            class="fa-toolbar-list-meta"
          >
            <span class="fa-toolbar-day-stat">{{ dayCountLabel }}</span>
            <PageToolbarSearch v-model="teamSearch" />
          </div>
        </n-layout-header>

        <div class="shell-content">
          <router-view v-slot="{ Component }">
            <keep-alive v-if="!isPhone" :include="['Predictions', 'Results']">
              <component :is="Component" />
            </keep-alive>
            <component v-else :is="Component" />
          </router-view>
        </div>
      </n-layout>
    </n-layout>

    <n-drawer
      v-if="isPhone && showShellLeagueNav"
      v-model:show="leagueDrawerShow"
      placement="left"
      width="88%"
      to="body"
      display-directive="if"
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
          :count-by-league="shellCountByLeague"
          :total-count="shellTotalCount"
          :loading="contentLoading"
          :collapsed="false"
          @select="selectLeague"
        >
          <template #filter>
            <LeagueFilterTrigger
              drawer-mode
              :options="shellFilterOptions"
              :tracked-ids="shellTrackedIds"
              :filter-active="shellFilterActive"
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

.league-sider {
  position: relative;
  z-index: 3;
  box-shadow: var(--fa-sider-shadow);
}

.shell-main > :deep(.fa-page-toolbar) {
  box-shadow: var(--fa-header-shadow);
}

.league-trigger {
  flex-shrink: 0;
}

.results-future-header {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.results-future-header .fa-toolbar-crumb {
  flex: 0 1 auto;
  max-width: 40%;
}

.results-future-dates {
  flex: 1;
  min-width: 0;
}

.results-future-dates :deep(.date-strip) {
  margin: 0 auto;
  padding-bottom: 4px;
}

:deep(.league-drawer .n-drawer-body-content-wrapper) {
  height: 100%;
}

:deep(.league-drawer .league-menu) {
  height: 100%;
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

:deep(.shell-layout > .n-layout-sider > .n-scrollbar) {
  height: 100%;
  max-height: 100%;
}

:deep(.shell-layout > .n-layout-sider > .n-scrollbar > .n-scrollbar-container) {
  max-height: 100%;
}

:deep(.shell-layout > .n-layout-sider > .n-scrollbar .n-scrollbar-content) {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
