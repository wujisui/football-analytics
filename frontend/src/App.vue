<script setup lang="ts">
import { NConfigProvider, NLayout, NLayoutContent, NLayoutHeader, zhCN } from 'naive-ui'
</script>

<template>
  <n-config-provider :locale="zhCN">
    <n-layout class="app-layout">
      <n-layout-header bordered class="app-header">
        <div class="brand" @click="$router.push({ name: 'leagues' })">
          <span class="brand-title">Football Analytics</span>
          <span class="brand-subtitle">足球数据分析</span>
        </div>
      </n-layout-header>

      <n-layout-content class="app-content">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-config-provider>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
}

.app-header {
  display: flex;
  align-items: center;
  padding: 0 24px;
  height: 64px;
}

.brand {
  display: flex;
  flex-direction: column;
  cursor: pointer;
}

.brand-title {
  font-size: 18px;
  font-weight: 700;
}

.brand-subtitle {
  font-size: 12px;
  color: #666;
}

.app-content {
  padding: 24px;
  max-width: 1100px;
  margin: 0 auto;
}
</style>
