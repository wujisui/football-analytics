<script setup lang="ts">
import type { DataTableColumns } from 'naive-ui'
import {
  computed,
  h,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  provide,
  ref,
  useSlots,
  watch,
  type VNodeChild,
} from 'vue'

import type { FixtureResponse } from '@/api/types'
import DayExpandFixtures from '@/components/DayExpandFixtures.vue'
import FixtureCard from '@/components/FixtureCard.vue'
import VirtualCardList from '@/components/VirtualCardList.vue'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useMarkedFixture } from '@/composables/useMarkedFixture'
import type { DetailFrom } from '@/utils/detailNav'
import { isFixtureCardMarkClickIgnored } from '@/utils/fixtureCardMark'
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
    /**
     * Flat virtual-list row estimate (groupByDay=false), and min row height for
     * the expanded day's virtual data-table (groupByDay=true).
     */
    itemSize?: number
    /** Flat virtual-list padding (groupByDay=false only). */
    paddingTop?: number | string
    paddingBottom?: number | string
    /** 点卡片空白处留阅读标记，便于翻长列表定位 */
    markable?: boolean
  }>(),
  {
    groupByDay: true,
    from: 'predictions',
    date: null,
    itemSize: 168,
    paddingTop: 0,
    paddingBottom: 12,
    markable: false,
  },
)

const slots = useSlots()
const isPhone = useIsPhone()
const hasCardSlot = computed(() => !!slots.card)
const { isMarked, toggleMarked, clearMarked, retainIfPresent } = useMarkedFixture()

watch(
  () => props.fixtures.map((f) => f.fixture_id),
  (ids) => {
    if (!props.markable) return
    retainIfPresent(ids)
  },
)

watch(
  () => [props.date, props.from] as const,
  () => {
    if (props.markable) clearMarked()
  },
)

const listEl = ref<HTMLElement | null>(null)
/** Viewport for the expanded day's virtual table (list height − date row). */
const expandMaxHeight = ref(360)

const DAY_ROW_RESERVE_PX = 44
const CARD_GAP_PX = 10

const dayGroups = computed(() =>
  props.groupByDay ? groupFixturesByScheduleDay(props.fixtures) : [],
)

/** Accordion: at most one schedule day open. */
const expandedKeys = ref<string[]>([])

/** Predictions phone/desktop cards are fixed-height; fall back to itemSize. */
const fixtureMinRowHeight = computed(() => {
  if (props.itemSize !== 168) return props.itemSize
  // phone .fixture-slot 184 / desktop .fixture-row 147 + gap between cards
  return (isPhone.value ? 184 : 147) + CARD_GAP_PX
})

function onFixtureRowClick(event: MouseEvent, fixtureId: number) {
  if (!props.markable) return
  if (isFixtureCardMarkClickIgnored(event)) return
  toggleMarked(fixtureId)
}

function fixtureRowClass(fixtureId: number): Record<string, boolean> {
  return {
    'day-fixture-row': true,
    'fa-card-markable': props.markable,
    'is-marked': props.markable && isMarked(fixtureId),
  }
}

function renderFixture(fixture: FixtureResponse): VNodeChild {
  const body = hasCardSlot.value
    ? (slots.card?.({ fixture }) ?? [])
    : h(FixtureCard, { fixture, from: props.from, date: props.date })
  return h(
    'div',
    {
      class: fixtureRowClass(fixture.fixture_id),
      onClick: (event: MouseEvent) => onFixtureRowClick(event, fixture.fixture_id),
    },
    body,
  )
}

provide('fixtureListExpandMaxHeight', expandMaxHeight)
provide('fixtureListRenderFixture', renderFixture)

watch(
  dayGroups,
  (groups) => {
    if (!groups.length) {
      expandedKeys.value = []
      return
    }
    const current = expandedKeys.value[0]
    if (current && groups.some((g) => g.key === current)) return
    // Default: nearest / first day with fixtures.
    expandedKeys.value = [groups[0].key]
  },
  { immediate: true },
)

let listResizeObserver: ResizeObserver | null = null

function syncExpandMaxHeight() {
  const height = listEl.value?.clientHeight ?? 0
  // keep-alive 停用后 shell 被移出文档，clientHeight 归零；此时改高度会重建
  // 展开日的虚拟列表，下次激活就撞上空引用。保留上一次的可见高度。
  if (height <= 0) return
  expandMaxHeight.value = Math.max(200, Math.floor(height - DAY_ROW_RESERVE_PX))
}

function startResizeObserver() {
  listResizeObserver?.disconnect()
  listResizeObserver = null
  syncExpandMaxHeight()
  if (!listEl.value || typeof ResizeObserver === 'undefined') return
  listResizeObserver = new ResizeObserver(() => syncExpandMaxHeight())
  listResizeObserver.observe(listEl.value)
}

function stopResizeObserver() {
  listResizeObserver?.disconnect()
  listResizeObserver = null
}

onMounted(startResizeObserver)
onActivated(startResizeObserver)
onDeactivated(stopResizeObserver)
onBeforeUnmount(stopResizeObserver)

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

const dayColumns = computed<DataTableColumns<ScheduleDayGroup>>(() => {
  const minRowHeight = fixtureMinRowHeight.value
  return [
    {
      type: 'expand',
      // flexHeight forces table-layout: fixed — without a width both columns
      // would split the row in half.
      width: 36,
      renderExpand: (group) =>
        h(DayExpandFixtures, {
          fixtures: group.fixtures,
          minRowHeight,
        }),
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
  ]
})

function dayRowKey(group: ScheduleDayGroup) {
  return group.key
}

function toggleDay(key: string) {
  expandedKeys.value = expandedKeys.value[0] === key ? [] : [key]
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
  const next = keys.map(String)
  if (next.length <= 1) {
    expandedKeys.value = next
    return
  }
  // Accordion: keep the newly opened day only.
  const prev = new Set(expandedKeys.value)
  const added = next.find((k) => !prev.has(k))
  expandedKeys.value = [added ?? next[next.length - 1]]
}

function rowFixture(item: unknown): FixtureResponse {
  return (item as { fixture: FixtureResponse }).fixture
}
</script>

<template>
  <div ref="listEl" class="fixture-list">
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
        <div
          :class="fixtureRowClass(rowFixture(item).fixture_id)"
          @click="onFixtureRowClick($event, rowFixture(item).fixture_id)"
        >
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

/* The expanded day owns the visible scrollbar; the outer day scroller would
 * paint a second rail over the cards. Child chain keeps the inner table's
 * own rail. Wheel / touch scrolling is unaffected. */
.day-table
  > :deep(.n-data-table-wrapper)
  > .n-data-table-base-table
  > .n-data-table-base-table-body
  > .n-scrollbar-rail {
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
 * Expanded content is not a hoverable row — kill naive's tr:hover wash
 * without leaning on naive's private --n-merged-* tokens. Cards supply
 * their own opaque background. */
.day-table :deep(.n-data-table-tr--expanded:not(.day-row)),
.day-table :deep(.n-data-table-tr--expanded:not(.day-row):hover) {
  background-color: transparent;
}

.day-table :deep(.n-data-table-tr--expanded:not(.day-row) > .n-data-table-td),
.day-table :deep(.n-data-table-tr--expanded:not(.day-row):hover > .n-data-table-td) {
  padding: 0;
  background-color: transparent;
}

.day-table :deep(.day-title) {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  user-select: none;
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

.day-fixture-row,
.day-table :deep(.day-fixture-row) {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.empty {
  margin: 12px var(--fa-content-inline);
  padding: 48px 0;
  background: var(--fa-bg-elevated);
  border: 1px dashed var(--fa-border);
  border-radius: var(--fa-radius-card);
}
</style>
