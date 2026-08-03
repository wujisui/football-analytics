<script setup lang="ts">
import { computed, ref, useSlots, watch } from 'vue'

import type { FixtureResponse } from '@/api/types'
import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FixtureCard from '@/components/FixtureCard.vue'
import type { DetailFrom } from '@/utils/detailNav'
import { groupFixturesByScheduleDay } from '@/utils/fixtureDayGroups'

const props = withDefaults(
  defineProps<{
    fixtures: FixtureResponse[]
    emptyDescription?: string
    /** full = odds+prediction card; prediction = algorithm card only */
    mode?: 'full' | 'prediction'
    /** Date sections as flat accordion (Naive Collapse). */
    groupByDay?: boolean
    from?: DetailFrom
    date?: string | null
    /** Controlled expand (accordion name = day key). Omit for internal default. */
    expandedNames?: string | null
  }>(),
  { mode: 'full', groupByDay: true, from: 'home', date: null },
)

const emit = defineEmits<{
  'update:expandedNames': [value: string | null]
}>()

const slots = useSlots()
const hasCardSlot = computed(() => !!slots.card)
const controlled = computed(() => props.expandedNames !== undefined)
const internalExpanded = ref<string | null>(null)

const dayGroups = computed(() =>
  props.groupByDay ? groupFixturesByScheduleDay(props.fixtures) : [],
)

function firstDayKey(): string | null {
  return dayGroups.value[0]?.key ?? null
}

watch(
  dayGroups,
  (groups) => {
    const next = firstDayKey()
    if (controlled.value) {
      const cur = props.expandedNames ?? null
      if (cur && groups.some((g) => g.key === cur)) return
      if (cur !== next) emit('update:expandedNames', next)
      return
    }
    if (internalExpanded.value && groups.some((g) => g.key === internalExpanded.value)) {
      return
    }
    internalExpanded.value = next
  },
  { immediate: true },
)

function normalizeExpanded(
  value: string | number | Array<string | number> | null | undefined,
): string | null {
  if (value == null) return null
  if (Array.isArray(value)) {
    const first = value[0]
    return first == null ? null : String(first)
  }
  return String(value)
}

const collapseExpanded = computed({
  get: () => (controlled.value ? props.expandedNames ?? null : internalExpanded.value),
  set: (value: string | number | Array<string | number> | null) => {
    const next = normalizeExpanded(value)
    if (controlled.value) emit('update:expandedNames', next)
    else internalExpanded.value = next
  },
})
</script>

<template>
  <div class="fixture-list">
    <n-empty
      v-if="fixtures.length === 0"
      :description="emptyDescription || '近期暂无该联赛赛事'"
      class="empty"
    />
    <n-collapse
      v-else-if="groupByDay"
      class="fa-day-collapse"
      accordion
      display-directive="show"
      arrow-placement="right"
      :expanded-names="collapseExpanded"
      @update:expanded-names="collapseExpanded = $event"
    >
      <n-collapse-item
        v-for="group in dayGroups"
        :key="group.key"
        :name="group.key"
      >
        <template #header>
          <div class="fa-day-collapse-title">
            <span class="fa-day-collapse-title__label">{{ group.label }}</span>
            <span class="fa-day-collapse-title__count">{{ group.fixtures.length }} 场</span>
          </div>
        </template>
        <n-space vertical :size="10" class="day-cards">
          <template v-if="hasCardSlot">
            <template v-for="fixture in group.fixtures" :key="fixture.fixture_id">
              <slot name="card" :fixture="fixture" />
            </template>
          </template>
          <template v-else-if="mode === 'prediction'">
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
              :from="from"
              :date="date"
            />
          </template>
        </n-space>
      </n-collapse-item>
    </n-collapse>
    <n-space v-else vertical :size="10" class="day-cards">
      <template v-if="hasCardSlot">
        <template v-for="fixture in fixtures" :key="fixture.fixture_id">
          <slot name="card" :fixture="fixture" />
        </template>
      </template>
      <template v-else-if="mode === 'prediction'">
        <AlgorithmPredictionCard
          v-for="fixture in fixtures"
          :key="fixture.fixture_id"
          :fixture="fixture"
          standalone
          from="predictions"
        />
      </template>
      <template v-else>
        <FixtureCard
          v-for="fixture in fixtures"
          :key="fixture.fixture_id"
          :fixture="fixture"
          :from="from"
          :date="date"
        />
      </template>
    </n-space>
  </div>
</template>

<style scoped>
.fixture-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
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
