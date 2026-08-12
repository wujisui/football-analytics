<script setup lang="ts">
import { computed, ref } from 'vue'

import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import ResultFixtureCard from '@/components/ResultFixtureCard.vue'
import {
  favoriteHasPredictSnapshot,
  snapshotFromFavorite,
  type FavoriteFixtureRecord,
} from '@/composables/useFavoriteFixtures'
import { useIsPhone } from '@/composables/useMediaQuery'

const props = defineProps<{
  item: FavoriteFixtureRecord
}>()

const emit = defineEmits<{
  openDetail: [fixtureId: number]
}>()

const isPhone = useIsPhone()
const showOddsModal = ref(false)

const hasPredict = computed(() => favoriteHasPredictSnapshot(props.item))
const predictionSnapshot = computed(() => snapshotFromFavorite(props.item))
const highlightMarket = computed(() =>
  props.item.source === 'auto' ? props.item.auto_market || null : null,
)

/** Any settled fixture uses the same card as the results list. */
const isFinished = computed(() => {
  const status = (props.item.status || '').toLowerCase()
  if (status === 'finished') return true
  return props.item.home_goals != null && props.item.away_goals != null
})

function openDetail() {
  emit('openDetail', props.item.fixture_id)
}

function openOddsModal() {
  showOddsModal.value = true
}
</script>

<template>
  <ResultFixtureCard
    v-if="isFinished && isPhone"
    :fixture="item"
    odds-clickable
    @open-detail="openDetail"
    @open-odds="openOddsModal"
  />

  <n-card
    v-else-if="isFinished"
    size="small"
    :bordered="false"
    class="favorite-fixture-card"
  >
    <div class="summary-grid">
      <PreMatchOddsTable
        :odds="item.odds_snippet"
        link-middle-to-detail
        :fixture-id="item.fixture_id"
        from="favorites"
      />
      <ResultFixtureCard
        :fixture="item"
        show-probabilities
        @open-detail="openDetail"
      />
    </div>
  </n-card>

  <ResultFixtureCard
    v-else-if="isPhone"
    :fixture="item"
    prematch
    odds-clickable
    :prediction-snapshot="hasPredict ? predictionSnapshot : undefined"
    :highlight-market="highlightMarket"
    from="favorites"
    @open-odds="openOddsModal"
  />

  <n-card
    v-else
    size="small"
    :bordered="false"
    class="favorite-fixture-card"
  >
    <div class="summary-grid">
      <PreMatchOddsTable
        :odds="item.odds_snippet"
        link-middle-to-detail
        :fixture-id="item.fixture_id"
        from="favorites"
      />
      <ResultFixtureCard
        :fixture="item"
        prematch
        :prediction-snapshot="hasPredict ? predictionSnapshot : undefined"
        :highlight-market="highlightMarket"
        from="favorites"
      />
    </div>
  </n-card>

  <n-modal
    v-if="isPhone"
    v-model:show="showOddsModal"
    preset="card"
    title="赛前盘口"
    :style="{ width: 'min(360px, calc(100vw - 24px))' }"
    :segmented="{ content: true, footer: false }"
  >
    <PreMatchOddsTable
      :odds="item.odds_snippet"
      link-middle-to-detail
      :fixture-id="item.fixture_id"
      from="favorites"
    />
  </n-modal>
</template>

<style scoped>
.favorite-fixture-card {
  background: var(--fa-bg-elevated);
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
}

.summary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  align-items: stretch;
  min-width: 0;
  max-width: 100%;
}

.summary-grid > :deep(*) {
  min-width: 0;
}

.summary-grid :deep(.result-fixture-card) {
  height: 100%;
}
</style>
