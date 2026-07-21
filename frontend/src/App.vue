<script setup lang="ts">
import { MoonOutline, StarOutline, SunnyOutline } from '@vicons/ionicons5'
import {
  NConfigProvider,
  NIcon,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NMessageProvider,
  zhCN,
  dateZhCN,
} from 'naive-ui'
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useFavoritesDrawer } from '@/composables/useFavoritesDrawer'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useTheme } from '@/composables/useTheme'
import FavoritesDrawer from '@/components/FavoritesDrawer.vue'
import { parseDetailFrom } from '@/utils/detailNav'
import { fixturesRouteWithLeague } from '@/utils/fixturesLeagueFilter'

const route = useRoute()
const router = useRouter()
const isPhone = useIsPhone()
const { naiveTheme, themeOverrides, isDark, toggleTheme } = useTheme()
const { show: favoritesDrawerShow, toggle: toggleFavoritesDrawer } = useFavoritesDrawer()

const activeNav = computed(() => {
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

function goNav(name: 'home' | 'predictions' | 'results') {
  if (favoritesDrawerShow.value) toggleFavoritesDrawer()
  if (route.name === name) return
  void router.push(fixturesRouteWithLeague(name))
}

/** Phone home already shows prediction cards; hide Predictions route there. */
watch(
  [isPhone, () => route.name],
  ([phone, name]) => {
    if (phone && name === 'predictions') {
      void router.replace(fixturesRouteWithLeague('home'))
    }
  },
  { immediate: true },
)
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
      <n-layout-header bordered class="app-header" style="flex-shrink: 0;">
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
          <nav class="app-nav" aria-label="主导航">
            <div class="nav-seg" role="group" aria-label="页面切换">
              <button
                type="button"
                class="nav-seg-btn"
                :class="{ active: activeNav === 'home' }"
                @click="goNav('home')"
              >
                即时
              </button>
              <button
                v-if="!isPhone"
                type="button"
                class="nav-seg-btn"
                :class="{ active: activeNav === 'predictions' }"
                @click="goNav('predictions')"
              >
                预测
              </button>
              <button
                type="button"
                class="nav-seg-btn"
                :class="{ active: activeNav === 'results' }"
                @click="goNav('results')"
              >
                赛程
              </button>
              <button
                type="button"
                class="nav-seg-btn nav-seg-btn-icon"
                :class="{ active: activeNav === 'favorites' }"
                aria-label="收藏"
                @click="toggleFavoritesDrawer"
              >
                <n-icon :size="16" :component="StarOutline" />
                <span class="nav-seg-label">收藏</span>
              </button>
            </div>
          </nav>

          <n-tooltip placement="bottom">
            <template #trigger>
              <button
                type="button"
                class="theme-toggle"
                :aria-label="isDark ? '切换到浅色' : '切换到深色'"
                @click="toggleTheme"
              >
                <n-icon :size="18" :component="isDark ? MoonOutline : SunnyOutline" />
              </button>
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
        style="flex: 1; min-height: 0;"
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
  align-self: center;
  max-width: 100%;
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
  gap: 10px;
  margin-left: 8px;
}

.app-nav {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.nav-seg {
  display: inline-flex;
  align-items: center;
  padding: 3px;
  gap: 2px;
  border-radius: 10px;
  border: 1px solid var(--fa-border);
  background: var(--fa-bg-soft);
}

.nav-seg-btn {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--fa-text-secondary);
  font-size: 13px;
  font-weight: 600;
  padding: 6px 14px;
  border-radius: 7px;
  cursor: pointer;
  flex-shrink: 0;
  white-space: nowrap;
  line-height: 1.2;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.nav-seg-btn:hover {
  color: var(--fa-text);
  background: color-mix(in srgb, var(--fa-text) 6%, transparent);
}

.nav-seg-btn.active {
  color: var(--fa-text-strong, var(--fa-text));
  background: var(--fa-bg-elevated);
  box-shadow: 0 1px 3px var(--fa-hover-shadow);
}

.nav-seg-btn-icon {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding-inline: 10px;
}

.nav-seg-label {
  font-size: 13px;
}

.nav-seg-btn:focus-visible {
  outline: 2px solid color-mix(in srgb, currentColor 35%, transparent);
  outline-offset: 1px;
}

.theme-toggle {
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  margin: 0;
  padding: 0;
  border: 1px solid var(--fa-border);
  border-radius: 10px;
  background: var(--fa-bg-soft);
  color: var(--fa-text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}

.theme-toggle:hover {
  color: var(--fa-text-strong);
  border-color: var(--fa-hover-border);
  background: var(--fa-bg-elevated);
}

.theme-toggle:focus-visible {
  outline: 2px solid color-mix(in srgb, currentColor 35%, transparent);
  outline-offset: 1px;
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
    gap: 8px;
  }

  .brand {
    max-width: calc(100% - 220px);
  }

  .brand-title {
    font-size: 15px;
  }

  .brand-subtitle {
    display: none;
  }

  .nav-seg-btn {
    padding: 5px 9px;
    font-size: 12px;
  }

  .header-actions {
    gap: 8px;
  }

  .theme-toggle {
    width: 32px;
    height: 32px;
  }
}
</style>
