<script setup lang="ts">
import { computed } from 'vue'

import type { FixtureResponse } from '@/api/types'
import FixtureCard from '@/components/FixtureCard.vue'
import { formatDate, parseApiDate } from '@/utils/format'

const props = defineProps<{
  fixtures: FixtureResponse[]
  emptyDescription?: string
}>()

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
        <n-divider title-placement="left" class="day-divider">
          {{ group.label }}
          <n-text depth="3" class="day-count">
            · {{ group.fixtures.length }} 场
          </n-text>
        </n-divider>
        <n-space vertical :size="14">
          <FixtureCard
            v-for="fixture in group.fixtures"
            :key="fixture.fixture_id"
            :fixture="fixture"
          />
        </n-space>
      </section>
    </template>
  </div>
</template>

<style scoped>
.fixture-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.day-divider {
  margin-top: 4px;
  margin-bottom: 12px;
}

.day-count {
  font-weight: 400;
  margin-left: 2px;
}

.empty {
  padding: 48px 0;
  background: var(--fa-bg-elevated);
  border: 1px dashed var(--fa-border);
  border-radius: 8px;
}
</style>
