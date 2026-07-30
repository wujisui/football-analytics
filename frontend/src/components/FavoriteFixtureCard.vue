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

const homeName = computed(() => props.item.home_team_name || '—')
const awayName = computed(() => props.item.away_team_name || '—')

const hasPredict = computed(() => favoriteHasPredictSnapshot(props.item))
const predictionSnapshot = computed(() => snapshotFromFavorite(props.item))

/** Any settled fixture uses the same card as the results list. */
const isFinished = computed(() => {
  const status = (props.item.status || '').toLowerCase()
  if (status === 'finished') return true
  return props.item.home_goals != null && props.item.away_goals != null
})

const oddsModalTitle = computed(
  () => `${homeName.value} vs ${awayName.value} · 赛前盘口`,
)

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

  <article v-else-if="isFinished" class="favorite-fixture-card">
    <div class="summary-grid">
      <PreMatchOddsTable
        :odds="item.odds_snippet"
        :home-name="homeName"
        :away-name="awayName"
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
  </article>

  <ResultFixtureCard
    v-else-if="isPhone"
    :fixture="item"
    prematch
    :prediction-snapshot="hasPredict ? predictionSnapshot : undefined"
    from="favorites"
  />

  <article v-else class="favorite-fixture-card">
    <div class="summary-grid">
      <PreMatchOddsTable
        :odds="item.odds_snippet"
        :home-name="homeName"
        :away-name="awayName"
        link-middle-to-detail
        :fixture-id="item.fixture_id"
        from="favorites"
      />
      <ResultFixtureCard
        :fixture="item"
        prematch
        :prediction-snapshot="hasPredict ? predictionSnapshot : undefined"
        from="favorites"
      />
    </div>
  </article>

  <n-modal
    v-if="isPhone"
    v-model:show="showOddsModal"
    preset="card"
    :title="oddsModalTitle"
    :style="{ width: 'min(360px, calc(100vw - 24px))' }"
    :segmented="{ content: true, footer: false }"
  >
    <PreMatchOddsTable
      :odds="item.odds_snippet"
      :home-name="homeName"
      :away-name="awayName"
      link-middle-to-detail
      :fixture-id="item.fixture_id"
      from="favorites"
    />
  </n-modal>
</template>

<style scoped>
.favorite-fixture-card {
  background: var(--fa-bg-elevated);
  border: 1px solid var(--fa-border);
  border-radius: 8px;
  padding: 10px;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  overflow: hidden;
  cursor: default;
  user-select: text;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.favorite-fixture-card:hover {
  border-color: var(--fa-hover-border);
  box-shadow: 0 2px 10px var(--fa-hover-shadow);
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
  box-sizing: border-box;
}
</style>
