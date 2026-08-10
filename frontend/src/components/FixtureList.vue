<script setup lang="ts">
import type { DataTableColumns } from 'naive-ui'
import { computed, h, ref, useSlots, watch } from 'vue'

import type { FixtureResponse } from '@/api/types'
import FixtureCard from '@/components/FixtureCard.vue'
import VirtualCardList from '@/components/VirtualCardList.vue'
import type { DetailFrom } from '@/utils/detailNav'
import {
  groupFixturesByScheduleDay,
  type ScheduleDayGroup,
} from '@/utils/fixtureDayGroups'

const props = withDefaults(
  defineProps<{
    fixtures: FixtureResponse[]
    emptyDescription?: string
    /** Day rows expand into their fixtures (default). Flat virtual list when false. */
    groupByDay?: boolean
    from?: DetailFrom
    date?: string | null
    /** Flat virtual-list row estimate (groupByDay=false only). */
    itemSize?: number
    /** Flat virtual-list padding (groupByDay=false only). */
    paddingTop?: number | string
    paddingBottom?: number | string
  }>(),
  {
    groupByDay: true,
    from: 'predictions',
    date: null,
    itemSize: 168,
    paddingTop: 0,
    paddingBottom: 12,
  },
)

const slots = useSlots()
const hasCardSlot = computed(() => !!slots.card)

const dayGroups = computed(() =>
  props.groupByDay ? groupFixturesByScheduleDay(props.fixtures) : [],
)

const expandedKeys = ref<string[]>([])

/** New days open on arrival; a day the user collapsed stays collapsed. */
watch(
  dayGroups,
  (groups, previous) => {
    const known = new Set((previous ?? []).map((g) => g.key))
    const open = new Set(expandedKeys.value)
    expandedKeys.value = groups
      .filter((g) => !known.has(g.key) || open.has(g.key))
      .map((g) => g.key)
  },
  { immediate: true },
)

const flatVirtualItems = computed(() =>
  props.fixtures.map((fixture) => ({
    key: `f-${fixture.fixture_id}`,
    fixture,
  })),
)

const flatItemsStyle: Record<string, string> = {
  paddingLeft: 'var(--fa-content-inline)',
  paddingRight: 'var(--fa-content-inline)',
  boxSizing: 'border-box',
}

function renderFixture(fixture: FixtureResponse) {
  if (hasCardSlot.value) return slots.card?.({ fixture }) ?? []
  return h(FixtureCard, { fixture, from: props.from, date: props.date })
}

const dayColumns = computed<DataTableColumns<ScheduleDayGroup>>(() => [
  {
    type: 'expand',
    // flexHeight forces table-layout: fixed — without a width both columns
    // would split the row in half.
    width: 36,
    renderExpand: (group) =>
      h(
        'div',
        { class: 'day-expand' },
        group.fixtures.map((fixture) =>
          h(
            'div',
            { class: 'day-fixture-row', key: fixture.fixture_id },
            renderFixture(fixture),
          ),
        ),
      ),
  },
  {
    key: 'label',
    render: (group) =>
      h('div', { class: 'day-title' }, [
        h('span', { class: 'day-title__label' }, group.label),
        h(
          'span',
          { class: 'day-title__count' },
          `共 ${group.fixtures.length} 场比赛`,
        ),
      ]),
  },
])

function dayRowKey(group: ScheduleDayGroup) {
  return group.key
}

function toggleDay(key: string) {
  const open = new Set(expandedKeys.value)
  if (!open.delete(key)) open.add(key)
  expandedKeys.value = [...open]
}

/** Whole date row toggles; the built-in trigger already handles its own click. */
function dayRowProps(group: ScheduleDayGroup) {
  return {
    class: 'day-row',
    onClick: (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest('.n-data-table-expand-trigger')) return
      toggleDay(group.key)
    },
  }
}

function onExpandedKeys(keys: Array<string | number>) {
  expandedKeys.value = keys.map(String)
}

function rowFixture(item: unknown): FixtureResponse {
  return (item as { fixture: FixtureResponse }).fixture
}
</script>

<template>
  <div class="fixture-list">
    <n-empty
      v-if="fixtures.length === 0"
      :description="emptyDescription || '近期暂无该联赛赛事'"
      class="empty"
    />

    <!-- Day rows are the date separators; fixtures live in the expanded area. -->
    <n-data-table
      v-else-if="groupByDay"
      class="day-table"
      :columns="dayColumns"
      :data="dayGroups"
      :row-key="dayRowKey"
      :row-props="dayRowProps"
      :expanded-row-keys="expandedKeys"
      :show-header="false"
      :bordered="false"
      :bottom-bordered="false"
      size="small"
      flex-height
      @update:expanded-row-keys="onExpandedKeys"
    />

    <!-- Flat schedule only: keep virtual list. -->
    <VirtualCardList
      v-else
      :items="flatVirtualItems"
      :item-size="itemSize"
      :item-resizable="false"
      :padding-top="paddingTop"
      :padding-bottom="paddingBottom"
      :items-style="flatItemsStyle"
    >
      <template #default="{ item }">
        <div class="day-fixture-row">
          <slot
            v-if="hasCardSlot"
            name="card"
            :fixture="rowFixture(item)"
          />
          <FixtureCard
            v-else
            :fixture="rowFixture(item)"
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

.day-table {
  flex: 1;
  min-height: 0;
}

/* flexHeight renders a discrete header element even with show-header=false. */
.day-table :deep(.n-data-table-base-table-header) {
  display: none;
}

/* Date row pins to the top of the body scroller while its day scrolls past;
 * the td background is opaque, so cards pass behind it. */
.day-table :deep(.day-row) {
  position: sticky;
  top: 0;
  z-index: 2;
  cursor: pointer;
}

/* Only the expanded area is flush; the date row keeps default row styling.
 * Expanded content is not a hoverable row — kill naive's tr:hover wash. */
.day-table :deep(.n-data-table-tr--expanded:not(.day-row):hover),
.day-table :deep(.n-data-table-tr--expanded:not(.day-row):hover > .n-data-table-td) {
  background-color: var(--n-merged-td-color);
}

.day-table :deep(.n-data-table-tr--expanded:not(.day-row) > .n-data-table-td) {
  padding: 0;
}

.day-table :deep(.day-title) {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.day-table :deep(.day-title__label) {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.day-table :deep(.day-title__count) {
  flex-shrink: 0;
  opacity: 0.6;
  font-size: 12px;
}

.day-table :deep(.day-expand) {
  padding: 10px 10px 0;
}

.day-fixture-row,
.day-table :deep(.day-fixture-row) {
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
