<script setup lang="ts">
import {
  NConfigProvider,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NMessageProvider,
  zhCN,
  dateZhCN,
} from 'naive-ui'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useTheme } from '@/composables/useTheme'

const route = useRoute()
const router = useRouter()
const { naiveTheme, themeOverrides, isDark, toggleTheme } = useTheme()

const activeNav = computed(() => {
  if (route.name === 'results') return 'results'
  return 'home'
})

function goNav(name: 'home' | 'results') {
  if (route.name === name) return
  void router.push({ name })
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
      <n-layout-header bordered class="app-header" style="flex-shrink: 0;">
        <div
          class="brand"
          role="link"
          tabindex="0"
          @click="$router.push({ name: 'home' })"
          @keydown.enter="$router.push({ name: 'home' })"
        >
          <span class="brand-title">Football Analytics</span>
          <span class="brand-subtitle">赛前分析 · 人机协同</span>
        </div>

        <nav class="app-nav" aria-label="主导航">
          <button
            type="button"
            class="nav-link"
            :class="{ active: activeNav === 'home' }"
            @click="goNav('home')"
          >
            赛前
          </button>
          <button
            type="button"
            class="nav-link"
            :class="{ active: activeNav === 'results' }"
            @click="goNav('results')"
          >
            赛果
          </button>
        </nav>
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

      <!-- Bottom-right theme toggle (avoids header edge clipping). -->
      <button
        type="button"
        class="theme-fab"
        :title="isDark ? '切换到浅色' : '切换到深色'"
        :aria-label="isDark ? '切换到浅色' : '切换到深色'"
        @click="toggleTheme"
      >
        <svg
          v-if="isDark"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          width="20"
          height="20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            d="M12.1 2a9.9 9.9 0 0 0-1.1.06 8 8 0 1 0 10.94 10.94A9.95 9.95 0 0 1 12.1 2z"
          />
        </svg>
        <svg
          v-else
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          width="20"
          height="20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            d="M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0-5a1 1 0 0 1 1 1v1.5a1 1 0 1 1-2 0V3a1 1 0 0 1 1-1zm0 17.5a1 1 0 0 1 1 1V22a1 1 0 1 1-2 0v-1.5a1 1 0 0 1 1-1zM3 11a1 1 0 1 0 0 2h1.5a1 1 0 1 0 0-2H3zm16.5 0a1 1 0 1 0 0 2H21a1 1 0 1 0 0-2h-1.5zM5.64 5.64a1 1 0 0 1 1.41 0l1.06 1.06a1 1 0 1 1-1.41 1.41L5.64 7.05a1 1 0 0 1 0-1.41zm10.25 10.25a1 1 0 0 1 1.41 0l1.06 1.06a1 1 0 0 1-1.41 1.41l-1.06-1.06a1 1 0 0 1 0-1.41zM5.64 18.36a1 1 0 0 1 0-1.41l1.06-1.06a1 1 0 1 1 1.41 1.41l-1.06 1.06a1 1 0 0 1-1.41 0zm10.25-10.25a1 1 0 0 1 0-1.41l1.06-1.06a1 1 0 1 1 1.41 1.41l-1.06 1.06a1 1 0 0 1-1.41 0z"
          />
        </svg>
      </button>
    </n-layout>
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
  justify-content: space-between;
  gap: 12px;
  height: 56px;
  /* border-box: content-box + width:100% would overflow and clip the right nav */
  box-sizing: border-box;
  padding: env(safe-area-inset-top, 0px) max(16px, env(safe-area-inset-right, 0px)) 0
    max(16px, env(safe-area-inset-left, 0px));
  flex-shrink: 0;
  overflow: hidden;
}

.brand {
  display: flex;
  flex-direction: column;
  cursor: pointer;
  outline: none;
  flex: 1;
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

.app-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  margin-left: 8px;
}

.nav-link {
  appearance: none;
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0.62;
  font-size: 13px;
  font-weight: 600;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
  flex-shrink: 0;
  white-space: nowrap;
}

.nav-link:hover {
  opacity: 0.9;
  background: color-mix(in srgb, currentColor 8%, transparent);
}

.nav-link.active {
  opacity: 1;
  background: color-mix(in srgb, currentColor 12%, transparent);
}

.theme-fab {
  appearance: none;
  position: fixed;
  z-index: 1000;
  right: max(20px, env(safe-area-inset-right, 0px));
  bottom: max(20px, env(safe-area-inset-bottom, 0px));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  margin: 0;
  padding: 0;
  border: 1px solid var(--fa-border);
  border-radius: 50%;
  background: var(--fa-bg-elevated);
  color: var(--fa-text-secondary);
  box-shadow: 0 4px 14px var(--fa-hover-shadow);
  cursor: pointer;
}

.theme-fab:hover {
  color: var(--fa-text-strong);
  border-color: var(--fa-hover-border);
}

.theme-fab:focus-visible {
  outline: 2px solid color-mix(in srgb, currentColor 35%, transparent);
  outline-offset: 2px;
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

  .brand-title {
    font-size: 15px;
  }

  .brand-subtitle {
    display: none;
  }

  .nav-link {
    padding: 5px 8px;
    font-size: 12px;
  }

  .theme-fab {
    width: 42px;
    height: 42px;
    right: max(16px, env(safe-area-inset-right, 0px));
    bottom: max(16px, env(safe-area-inset-bottom, 0px));
  }
}
</style>
