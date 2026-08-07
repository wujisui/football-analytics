<script setup lang="ts">
import { computed, useSlots } from 'vue'

import type { FixtureResponse } from '@/api/types'
import FixtureCard from '@/components/FixtureCard.vue'
import VirtualCardList from '@/components/VirtualCardList.vue'
import type { DetailFrom } from '@/utils/detailNav'
import { groupFixturesByScheduleDay } from '@/utils/fixtureDayGroups'

const props = withDefaults(
  defineProps<{
    fixtures: FixtureResponse[]
    emptyDescription?: string
    /** Native sticky day sections (default). Flat virtual list when false. */
    groupByDay?: boolean
    from?: DetailFrom
    date?: string | null
    /** Flat virtual-list row estimate (groupByDay=false only). */
    itemSize?: number
    paddingTop?: number | string
    paddingBottom?: number | string
    itemsStyle?: string | Record<string, string>
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

const emit = defineEmits<{
  scroll: [event: Event]
}>()

const slots = useSlots()
const hasCardSlot = computed(() => !!slots.card)

const dayGroups = computed(() =>
  props.groupByDay ? groupFixturesByScheduleDay(props.fixtures) : [],
)

const flatVirtualItems = computed(() =>
  props.fixtures.map((fixture) => ({
    key: `f-${fixture.fixture_id}`,
    fixture,
  })),
)

const defaultItemsStyle = computed((): Record<string, string> => {
  if (props.itemsStyle && typeof props.itemsStyle === 'object') {
    return props.itemsStyle
  }
  return {
    paddingLeft: 'var(--fa-content-inline)',
    paddingRight: 'var(--fa-content-inline)',
    boxSizing: 'border-box',
  }
})

const dayScrollStyle = computed(() => {
  const padTop =
    typeof props.paddingTop === 'number'
      ? `${props.paddingTop}px`
      : String(props.paddingTop)
  const padBottom =
    typeof props.paddingBottom === 'number'
      ? `${props.paddingBottom}px`
      : String(props.paddingBottom)
  return {
    ...defaultItemsStyle.value,
    paddingTop: padTop,
    paddingBottom: padBottom,
  }
})

const flatItemsStyle = computed(() => props.itemsStyle ?? defaultItemsStyle.value)

function onDayScroll(event: Event) {
  emit('scroll', event)
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

    <!-- Day sections: native scroll + CSS sticky (no virtual list). -->
    <div
      v-else-if="groupByDay"
      class="fixture-list-scroll fa-scrollbar-hidden"
      :style="dayScrollStyle"
      @scroll.passive="onDayScroll"
    >
      <section
        v-for="group in dayGroups"
        :key="group.key"
        class="day-section"
      >
        <header class="day-sticky">
          <div class="fa-day-collapse-title">
            <n-ellipsis class="fa-day-collapse-title__label">
              {{ group.label }}
            </n-ellipsis>
            <span class="fa-day-collapse-title__count">
              {{ group.fixtures.length }} 场
            </span>
          </div>
        </header>
        <div
          v-for="fixture in group.fixtures"
          :key="fixture.fixture_id"
          class="day-fixture-row"
        >
          <slot v-if="hasCardSlot" name="card" :fixture="fixture" />
          <FixtureCard
            v-else
            :fixture="fixture"
            :from="from"
            :date="date"
          />
        </div>
      </section>
    </div>

    <!-- Flat schedule only: keep virtual list. -->
    <VirtualCardList
      v-else
      :items="flatVirtualItems"
      :item-size="itemSize"
      :item-resizable="false"
      :padding-top="paddingTop"
      :padding-bottom="paddingBottom"
      :items-style="flatItemsStyle"
      @scroll="emit('scroll', $event)"
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

.fixture-list-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
}

.day-section {
  min-width: 0;
}

.day-sticky {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  min-height: 40px;
  margin: 0 0 8px;
  padding: 8px 12px;
  box-sizing: border-box;
  border-radius: 8px;
  background: color-mix(in srgb, var(--fa-highlight-text) 12%, var(--fa-bg-soft));
  box-shadow: 0 1px 0 color-mix(in srgb, var(--fa-highlight-text) 10%, transparent);
}

.day-fixture-row {
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
