<script setup lang="ts">
import ResultFixtureCard from '@/components/ResultFixtureCard.vue'
import VirtualCardList from '@/components/VirtualCardList.vue'
import type { ResultFixture } from '@/api/fixtures'
import type { ResultsHitKey } from '@/utils/resultsPageState'

defineProps<{
  items: Record<string, unknown>[]
  empty: boolean
  emptyDescription: string
  contentLoading: boolean
  filterHitKey: ResultsHitKey | null
  paddingTop?: number
  paddingBottom?: number
  itemsStyle?: Record<string, string>
  /** 阅读标记：点卡片选中，便于翻列表时定位 */
  markedFixtureId?: number | null
}>()

const emit = defineEmits<{
  openDetail: [fixtureId: number]
  filterHit: [key: ResultsHitKey]
  toggleSelect: [fixtureId: number]
}>()

function rowFixture(item: unknown): ResultFixture {
  return (item as { fixture: ResultFixture }).fixture
}
</script>

<template>
  <n-empty
    v-if="empty"
    :description="emptyDescription"
    class="results-virtual-empty"
  />
  <VirtualCardList
    v-else
    :items="items"
    :item-size="128"
    :padding-top="paddingTop ?? 4"
    :padding-bottom="paddingBottom ?? 12"
    :items-style="itemsStyle"
  >
    <template #default="{ item }">
      <div class="results-virtual-row">
        <ResultFixtureCard
          :fixture="rowFixture(item)"
          :show-date="false"
          hit-filterable
          :active-hit-key="filterHitKey"
          selectable
          :selected="markedFixtureId === rowFixture(item).fixture_id"
          @open-detail="emit('openDetail', $event)"
          @filter-hit="emit('filterHit', $event)"
          @toggle-select="emit('toggleSelect', $event)"
        />
      </div>
    </template>
  </VirtualCardList>
  <div
    v-if="contentLoading"
    class="list-loading-mask"
    aria-busy="true"
    aria-live="polite"
  >
    <n-spin :show="true" />
  </div>
</template>

<style scoped>
.results-virtual-row {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  padding-bottom: 10px;
  box-sizing: border-box;
}

.results-virtual-empty {
  padding: 32px 0;
}

.list-loading-mask {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--fa-bg) 62%, transparent);
  pointer-events: none;
}
</style>
