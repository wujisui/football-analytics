<script setup lang="ts">
import { ChevronDownOutline } from '@vicons/ionicons5'
import { computed, ref, useSlots, watch } from 'vue'

import type { FixtureResponse } from '@/api/types'
import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FixtureCard from '@/components/FixtureCard.vue'
import VirtualCardList from '@/components/VirtualCardList.vue'
import type { DetailFrom } from '@/utils/detailNav'
import { groupFixturesByScheduleDay } from '@/utils/fixtureDayGroups'

const props = withDefaults(
  defineProps<{
    fixtures: FixtureResponse[]
    emptyDescription?: string
    /** full = odds+prediction card; prediction = algorithm card only */
    mode?: 'full' | 'prediction'
    /** Date sections as accordion headers inside the virtual list. */
    groupByDay?: boolean
    from?: DetailFrom
    date?: string | null
    /** Controlled expand (accordion name = day key). Omit for internal default. */
    expandedNames?: string | null
    /** Estimated row height before resize measure. */
    itemSize?: number
    paddingTop?: number | string
    paddingBottom?: number | string
    itemsStyle?: string | Record<string, string>
  }>(),
  {
    mode: 'full',
    groupByDay: true,
    from: 'home',
    date: null,
    itemSize: 168,
    paddingTop: 0,
    paddingBottom: 12,
  },
)

const emit = defineEmits<{
  'update:expandedNames': [value: string | null]
  scroll: [event: Event]
}>()

type DayRow = {
  key: string
  kind: 'day'
  dayKey: string
  label: string
  count: number
}

type FixtureRow = {
  key: string
  kind: 'fixture'
  fixture: FixtureResponse
}

type VirtualRow = DayRow | FixtureRow

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
    if (
      internalExpanded.value &&
      groups.some((g) => g.key === internalExpanded.value)
    ) {
      return
    }
    internalExpanded.value = next
  },
  { immediate: true },
)

const expandedDay = computed({
  get: () =>
    controlled.value ? props.expandedNames ?? null : internalExpanded.value,
  set: (value: string | null) => {
    if (controlled.value) emit('update:expandedNames', value)
    else internalExpanded.value = value
  },
})

function toggleDay(dayKey: string) {
  expandedDay.value = expandedDay.value === dayKey ? null : dayKey
}

const virtualRows = computed((): VirtualRow[] => {
  if (!props.fixtures.length) return []
  if (!props.groupByDay) {
    return props.fixtures.map((fixture) => ({
      key: `f-${fixture.fixture_id}`,
      kind: 'fixture' as const,
      fixture,
    }))
  }

  const rows: VirtualRow[] = []
  const open = expandedDay.value
  for (const group of dayGroups.value) {
    rows.push({
      key: `d-${group.key}`,
      kind: 'day',
      dayKey: group.key,
      label: group.label,
      count: group.fixtures.length,
    })
    if (open !== group.key) continue
    for (const fixture of group.fixtures) {
      rows.push({
        key: `f-${fixture.fixture_id}`,
        kind: 'fixture',
        fixture,
      })
    }
  }
  return rows
})

/** n-virtual-list item bags are plain records; keep typed accessors for the slot. */
const virtualItems = computed(() => virtualRows.value as unknown as Record<string, unknown>[])

function asVirtualRow(item: unknown): VirtualRow {
  return item as VirtualRow
}

const defaultItemsStyle = computed(() => {
  if (props.itemsStyle) return props.itemsStyle
  return {
    paddingLeft: 'var(--fa-content-inline)',
    paddingRight: 'var(--fa-content-inline)',
    boxSizing: 'border-box',
  }
})
</script>

<template>
  <div class="fixture-list">
    <n-empty
      v-if="fixtures.length === 0"
      :description="emptyDescription || '近期暂无该联赛赛事'"
      class="empty"
    />
    <VirtualCardList
      v-else
      :items="virtualItems"
      :item-size="itemSize"
      :padding-top="paddingTop"
      :padding-bottom="paddingBottom"
      :items-style="defaultItemsStyle"
      @scroll="emit('scroll', $event)"
    >
      <template #default="{ item }">
        <div
          v-if="asVirtualRow(item).kind === 'day'"
          class="virtual-day-header"
          role="button"
          tabindex="0"
          :aria-expanded="expandedDay === (asVirtualRow(item) as DayRow).dayKey"
          @click="toggleDay((asVirtualRow(item) as DayRow).dayKey)"
          @keydown.enter.prevent="toggleDay((asVirtualRow(item) as DayRow).dayKey)"
          @keydown.space.prevent="toggleDay((asVirtualRow(item) as DayRow).dayKey)"
        >
          <div class="fa-day-collapse-title">
            <span class="fa-day-collapse-title__label">{{ (asVirtualRow(item) as DayRow).label }}</span>
            <span class="fa-day-collapse-title__count">{{ (asVirtualRow(item) as DayRow).count }} 场</span>
          </div>
          <n-icon
            class="virtual-day-chevron"
            :class="{ open: expandedDay === (asVirtualRow(item) as DayRow).dayKey }"
            :component="ChevronDownOutline"
            :size="16"
          />
        </div>
        <div v-else class="virtual-fixture-row">
          <slot
            v-if="hasCardSlot"
            name="card"
            :fixture="(asVirtualRow(item) as FixtureRow).fixture"
          />
          <AlgorithmPredictionCard
            v-else-if="mode === 'prediction'"
            :fixture="(asVirtualRow(item) as FixtureRow).fixture"
            standalone
            from="predictions"
          />
          <FixtureCard
            v-else
            :fixture="(asVirtualRow(item) as FixtureRow).fixture"
            :from="from"
            :date="date"
          />
        </div>
      </template>
    </VirtualCardList>
  </div>
</template>

<style scoped>
.fixture-list {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.virtual-day-header {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  margin: 0 0 8px;
  padding: 8px 12px;
  box-sizing: border-box;
  border-radius: 8px;
  background: var(--fa-bg-soft);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.virtual-day-header:focus-visible {
  outline: 2px solid var(--fa-highlight-text, #18a058);
  outline-offset: 1px;
}

.virtual-day-chevron {
  flex-shrink: 0;
  margin-left: auto;
  opacity: 0.65;
  transition: transform 0.15s ease;
}

.virtual-day-chevron.open {
  transform: rotate(180deg);
}

.virtual-fixture-row {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  padding-bottom: 10px;
  box-sizing: border-box;
}

.empty {
  margin: 12px var(--fa-content-inline);
  padding: 48px 0;
  background: var(--fa-bg-elevated);
  border: 1px dashed var(--fa-border);
  border-radius: 8px;
}
</style>
