<script setup lang="ts">
import { computed } from 'vue'

import type { FixtureResponse } from '@/api/types'
import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FixtureCard from '@/components/FixtureCard.vue'
import { formatDate, parseApiDate } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    fixtures: FixtureResponse[]
    emptyDescription?: string
    /** full = odds+prediction card; prediction = algorithm card only */
    mode?: 'full' | 'prediction'
  }>(),
  { mode: 'full' },
)

type DayGroup = {
  key: string
  label: string
  fixtures: FixtureResponse[]
}

function localDayKey(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function daySectionLabel(sampleIso: string): string {
  const pretty = formatDate(sampleIso)
  return pretty || sampleIso.slice(0, 10)
}

const dayGroups = computed((): DayGroup[] => {
  const map = new Map<string, FixtureResponse[]>()
  for (const f of props.fixtures) {
    const d = parseApiDate(f.fixture_date)
    const key = Number.isNaN(d.getTime())
      ? String(f.fixture_date).slice(0, 10)
      : localDayKey(d)
    const bucket = map.get(key)
    if (bucket) bucket.push(f)
    else map.set(key, [f])
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, fixtures]) => ({
      key,
      label: daySectionLabel(fixtures[0].fixture_date),
      fixtures,
    }))
})
</script>

<template>
  <div class="fixture-list">
    <n-empty
      v-if="fixtures.length === 0"
      :description="emptyDescription || '近期暂无该联赛赛事'"
      class="empty"
    />
    <template v-else>
      <section
        v-for="group in dayGroups"
        :key="group.key"
        class="day-section"
      >
        <n-flex class="section-band" justify="space-between" align="center" :size="12">
          <n-flex align="center" :size="8">
            <span class="title-bar" aria-hidden="true" />
            <n-text strong style="font-size: 15px">{{ group.label }}</n-text>
          </n-flex>
          <n-text depth="3" style="font-size: 13px; white-space: nowrap">
            {{ group.fixtures.length }} 场
          </n-text>
        </n-flex>
        <n-space vertical :size="14" class="day-cards">
          <template v-if="mode === 'prediction'">
            <AlgorithmPredictionCard
              v-for="fixture in group.fixtures"
              :key="fixture.fixture_id"
              :fixture="fixture"
              standalone
              from="predictions"
            />
          </template>
          <template v-else>
            <FixtureCard
              v-for="fixture in group.fixtures"
              :key="fixture.fixture_id"
              :fixture="fixture"
            />
          </template>
        </n-space>
      </section>
    </template>
  </div>
</template>

<style scoped>
.fixture-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.day-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-band {
  padding: 10px 12px;
  background: var(--fa-bg-soft);
  border-radius: 6px;
}

.title-bar {
  width: 3px;
  height: 14px;
  border-radius: 1px;
  background: #c23b3b;
  flex-shrink: 0;
}

.day-cards {
  width: 100%;
}

.empty {
  padding: 48px 0;
  background: var(--fa-bg-elevated);
  border: 1px dashed var(--fa-border);
  border-radius: 8px;
}
</style>
