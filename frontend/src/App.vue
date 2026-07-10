<script setup lang="ts">
import {
  NConfigProvider,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NSelect,
  zhCN,
  dateZhCN,
} from 'naive-ui'

import { useTheme } from '@/composables/useTheme'
import type { ThemePresetId } from '@/theme/presets'

const { naiveTheme, themeOverrides, themeOptions, presetId, setPreset } = useTheme()

function onThemeChange(value: string) {
  setPreset(value as ThemePresetId)
}
</script>

<template>
  <n-config-provider
    :locale="zhCN"
    :date-locale="dateZhCN"
    :theme="naiveTheme"
    :theme-overrides="themeOverrides"
  >
    <n-layout class="app-shell" position="absolute">
      <n-layout-header bordered class="app-header">
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
        content-style="height: 100%; overflow: hidden; position: relative;"
      >
        <router-view />
      </n-layout-content>
    </n-layout>
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
  gap: 16px;
  height: 56px;
  padding: 0 20px;
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

.theme-select {
  width: 168px;
  flex-shrink: 0;
}

.app-body {
  flex: 1;
  min-height: 0;
  height: calc(100vh - 56px);
}
</style>
