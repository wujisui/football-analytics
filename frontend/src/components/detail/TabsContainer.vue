<script setup lang="ts">
import { ref, watch } from 'vue'

import H2HTab from '@/components/detail/H2HTab.vue'
import LineupTab from '@/components/detail/LineupTab.vue'
import PredictionTab from '@/components/detail/PredictionTab.vue'
import StatsTab from '@/components/detail/StatsTab.vue'
import type { FixtureResponse, PrematchPackage } from '@/api/types'

type TabKey = 'record' | 'stats' | 'lineup' | 'prediction'

const props = defineProps<{
  fixture: FixtureResponse
  pkg: PrematchPackage | null
  loading?: boolean
  error?: string
}>()

defineEmits<{
  retry: []
}>()

const activeTab = ref<TabKey>('record')
/** Mount tab content only after first visit (lazy UI); data already from /analysis. */
const visited = ref<Set<TabKey>>(new Set(['record']))

const tabs: { name: TabKey; label: string }[] = [
  { name: 'record', label: '战绩与交锋' },
  { name: 'stats', label: '赛季数据' },
  { name: 'lineup', label: '伤病与阵容' },
  { name: 'prediction', label: '我的预测' },
]

function onTabChange(name: string) {
  const key = name as TabKey
  activeTab.value = key
  if (!visited.value.has(key)) {
    visited.value = new Set([...visited.value, key])
  }
}

watch(
  () => props.fixture.fixture_id,
  () => {
    activeTab.value = 'record'
    visited.value = new Set(['record'])
  },
)
</script>

<template>
  <div class="tabs-container">
    <n-tabs
      :value="activeTab"
      type="line"
      :animated="false"
      @update:value="onTabChange"
    >
      <n-tab-pane
        v-for="tab in tabs"
        :key="tab.name"
        :name="tab.name"
        :tab="tab.label"
        display-directive="show:lazy"
      >
        <div class="pane">
          <n-spin :show="!!loading">
            <n-scrollbar class="pane-scroll" trigger="hover">
              <div class="pane-body">
                <n-alert v-if="error" type="error" :title="error">
                  <n-button size="small" type="primary" @click="$emit('retry')">重试</n-button>
                </n-alert>

                <template v-else-if="visited.has(tab.name)">
                  <H2HTab
                    v-if="tab.name === 'record'"
                    :home-team-name="fixture.home_team_name"
                    :away-team-name="fixture.away_team_name"
                    :home-team-id="fixture.home_team_id"
                    :away-team-id="fixture.away_team_id"
                    :pkg="pkg"
                  />
                  <StatsTab
                    v-else-if="tab.name === 'stats'"
                    :fixture="fixture"
                    :pkg="pkg"
                  />
                  <LineupTab
                    v-else-if="tab.name === 'lineup'"
                    :fixture="fixture"
                    :pkg="pkg"
                  />
                  <PredictionTab
                    v-else-if="tab.name === 'prediction'"
                    :fixture="fixture"
                  />
                </template>
              </div>
            </n-scrollbar>
          </n-spin>
        </div>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.tabs-container {
  background: var(--fa-bg-elevated);
  border: 1px solid var(--fa-border);
  border-radius: 8px;
  padding: 8px 16px 12px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tabs-container :deep(.n-tabs) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tabs-container :deep(.n-tabs-nav) {
  flex-shrink: 0;
}

.tabs-container :deep(.n-tabs-content),
.tabs-container :deep(.n-tab-pane),
.tabs-container :deep(.n-tabs-pane-wrapper),
.tabs-container :deep(.n-tabs-pane-wrapper > div) {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.pane {
  flex: 1;
  min-height: 0;
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.pane :deep(.n-spin-container),
.pane :deep(.n-spin-body),
.pane :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.pane-scroll {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.pane-body {
  padding-right: 8px;
  padding-bottom: 12px;
}
</style>
