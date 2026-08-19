<script setup lang="ts">
import type { DataTableColumns, DataTableRowKey } from 'naive-ui'
import { computed, inject, type Ref, type VNodeChild } from 'vue'

import type { FixtureResponse } from '@/api/types'

defineProps<{
  fixtures: FixtureResponse[]
  minRowHeight: number
}>()

const expandMaxHeight = inject<Ref<number>>('fixtureListExpandMaxHeight')
const renderFixture = inject<(fixture: FixtureResponse) => VNodeChild>(
  'fixtureListRenderFixture',
)

const maxHeight = computed(() => expandMaxHeight?.value ?? 360)

function rowKey(fixture: FixtureResponse): DataTableRowKey {
  return fixture.fixture_id
}

const columns = computed<DataTableColumns<FixtureResponse>>(() => [
  {
    key: 'card',
    render: (fixture) =>
      renderFixture ? renderFixture(fixture) : fixture.fixture_id,
  },
])
</script>

<template>
  <div class="day-expand" :style="{ height: `${maxHeight}px` }">
    <n-data-table
      class="day-fixture-table"
      :columns="columns"
      :data="fixtures"
      :row-key="rowKey"
      :show-header="false"
      :bordered="false"
      :bottom-bordered="false"
      size="small"
      flex-height
      virtual-scroll
      :min-row-height="minRowHeight"
    />
  </div>
</template>

<style scoped>
.day-expand {
  box-sizing: border-box;
  min-height: 0;
}

.day-fixture-table {
  height: 100%;
  background: transparent;
}

.day-fixture-table :deep(.n-data-table-base-table-header) {
  display: none;
}

.day-fixture-table :deep(.n-data-table-td) {
  padding: 5px;
  background: transparent;
  border: none;
}

.day-fixture-table :deep(.n-data-table-tr:hover > .n-data-table-td) {
  background: transparent;
}
</style>
