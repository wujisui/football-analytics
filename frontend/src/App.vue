<script setup lang="ts">
import {
  NConfigProvider,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NMessageProvider,
  NSelect,
  zhCN,
  dateZhCN,
} from 'naive-ui'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useTheme } from '@/composables/useTheme'
import type { ThemePresetId } from '@/theme/presets'

const route = useRoute()
const router = useRouter()
const { naiveTheme, themeOverrides, themeOptions, presetId, setPreset } = useTheme()

function onThemeChange(value: string) {
  setPreset(value as ThemePresetId)
}

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

        <n-select
          class="theme-select"
          size="small"
          :value="presetId"
          :options="themeOptions"
          :consistent-menu-width="false"
          placeholder="主题"
          @update:value="onThemeChange"
        />
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
  padding: 0 16px;
  padding-top: env(safe-area-inset-top, 0px);
  box-sizing: content-box;
  flex-shrink: 0;
}

.brand {
  display: flex;
  flex-direction: column;
  cursor: pointer;
  outline: none;
  min-width: 0;
}

.brand:focus-visible {
  opacity: 0.8;
}

.brand-title {
  font-size: 17px;
  font-weight: 700;
  line-height: 1.2;
}

.brand-subtitle {
  font-size: 11px;
  opacity: 0.65;
  line-height: 1.2;
}

.app-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  margin-right: 8px;
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
}

.nav-link:hover {
  opacity: 0.9;
  background: color-mix(in srgb, currentColor 8%, transparent);
}

.nav-link.active {
  opacity: 1;
  background: color-mix(in srgb, currentColor 12%, transparent);
}

.theme-select {
  width: 148px;
  flex-shrink: 0;
}

.app-body {
  flex: 1;
  min-height: 0;
}

@media (max-width: 767px) {
  .app-header {
    height: 48px;
    padding-left: 12px;
    padding-right: 12px;
    gap: 8px;
  }

  .brand-title {
    font-size: 15px;
  }

  .brand-subtitle {
    display: none;
  }

  .app-nav {
    margin-right: 4px;
  }

  .nav-link {
    padding: 5px 8px;
    font-size: 12px;
  }

  .theme-select {
    width: 112px;
  }
}
</style>
