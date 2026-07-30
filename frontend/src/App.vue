<script setup lang="ts">
import { MoonOutline, StarOutline, SunnyOutline } from '@vicons/ionicons5'
import {
  NButton,
  NButtonGroup,
  NConfigProvider,
  NIcon,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NMessageProvider,
  NTooltip,
  zhCN,
  dateZhCN,
} from 'naive-ui'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useFavoritesDrawer } from '@/composables/useFavoritesDrawer'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useTheme } from '@/composables/useTheme'
import FavoritesDrawer from '@/components/FavoritesDrawer.vue'
import { parseDetailFrom } from '@/utils/detailNav'
import { fixturesRouteWithLeague } from '@/utils/fixturesLeagueFilter'

type NavKey = 'home' | 'predictions' | 'results' | 'favorites'

const route = useRoute()
const router = useRouter()
const isPhone = useIsPhone()
const { naiveTheme, themeOverrides, isDark, toggleTheme } = useTheme()
const { show: favoritesDrawerShow, toggle: toggleFavoritesDrawer } = useFavoritesDrawer()

const activeNav = computed<NavKey>(() => {
  if (favoritesDrawerShow.value) return 'favorites'
  if (route.name === 'results') return 'results'
  if (route.name === 'predictions') return 'predictions'
  if (route.name === 'fixture-detail') {
    const from = parseDetailFrom(route.query.from)
    if (from === 'favorites') return 'favorites'
    if (from === 'results') return 'results'
    if (from === 'predictions') return 'predictions'
  }
  return 'home'
})

function navType(key: NavKey) {
  return activeNav.value === key ? 'primary' : 'default'
}

function goNav(name: 'home' | 'predictions' | 'results') {
  if (favoritesDrawerShow.value) toggleFavoritesDrawer()
  if (route.name === name) return
  void router.push(fixturesRouteWithLeague(name))
}
</script>

<template>
  <n-config-provider
    :locale="zhCN"
    :date-locale="dateZhCN"
    :theme="naiveTheme"
    :theme-overrides="themeOverrides"
  >
    <n-message-provider>
      <n-layout
        class="app-shell"
        position="absolute"
        content-style="display: flex; flex-direction: column; height: 100%;"
      >
        <n-layout-header bordered class="app-header">
          <div class="app-header-inner">
            <div
              class="brand"
              role="link"
              tabindex="0"
              @click="goNav('home')"
              @keydown.enter="goNav('home')"
            >
              <span class="brand-title">Football Analytics</span>
              <span class="brand-subtitle">赛前分析 · 人机协同</span>
            </div>

            <div class="header-actions">
              <n-button-group size="small">
                <n-button :type="navType('home')" @click="goNav('home')">即时</n-button>
                <n-button
                  :type="navType('predictions')"
                  @click="goNav('predictions')"
                >
                  {{ isPhone ? '计算器' : '预测' }}
                </n-button>
                <n-button :type="navType('results')" @click="goNav('results')">赛程</n-button>
                <n-button
                  :type="navType('favorites')"
                  aria-label="收藏"
                  @click="toggleFavoritesDrawer"
                >
                  <template #icon>
                    <n-icon :component="StarOutline" />
                  </template>
                  收藏
                </n-button>
              </n-button-group>

              <n-tooltip placement="bottom">
                <template #trigger>
                  <n-button
                    size="small"
                    quaternary
                    :aria-label="isDark ? '切换到浅色' : '切换到深色'"
                    @click="toggleTheme"
                  >
                    <template #icon>
                      <n-icon :component="isDark ? MoonOutline : SunnyOutline" />
                    </template>
                  </n-button>
                </template>
                {{ isDark ? '切换到浅色' : '切换到深色' }}
              </n-tooltip>
            </div>
          </div>
        </n-layout-header>

        <n-layout-content
          class="app-body"
          :native-scrollbar="false"
          :scrollbar-props="{ trigger: 'hover' }"
          content-style="height: 100%; overflow: hidden; position: relative;"
        >
          <router-view />
        </n-layout-content>
      </n-layout>
      <FavoritesDrawer />
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
.app-shell {
  inset: 0;
  background: var(--fa-bg);
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 56px;
  box-sizing: border-box;
  padding: env(safe-area-inset-top, 0px) max(16px, env(safe-area-inset-right, 0px)) 0
    max(16px, env(safe-area-inset-left, 0px));
  flex-shrink: 0;
  overflow: hidden;
  background: var(--fa-bg-elevated);
}

.app-header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  max-width: var(--fa-page-max-width);
  height: 100%;
  box-sizing: border-box;
}

.brand {
  display: flex;
  flex-direction: column;
  cursor: pointer;
  outline: none;
  flex: 0 1 auto;
  min-width: 0;
}

.brand:focus-visible {
  opacity: 0.8;
}

.brand-title {
  font-size: 17px;
  font-weight: 700;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brand-subtitle {
  font-size: 11px;
  opacity: 0.65;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 8px;
  margin-left: 8px;
}

.app-body {
  flex: 1;
  min-height: 0;
}

@media (max-width: 767px) {
  .app-header {
    height: 48px;
    padding-left: max(12px, env(safe-area-inset-left, 0px));
    padding-right: max(12px, env(safe-area-inset-right, 0px));
  }

  .brand {
    max-width: calc(100% - 248px);
  }

  .brand-title {
    font-size: 15px;
  }

  .brand-subtitle {
    display: none;
  }
}
</style>
