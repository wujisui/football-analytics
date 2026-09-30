<script setup lang="ts">
import { computed, ref } from 'vue'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import PreMatchOddsModal from '@/components/PreMatchOddsModal.vue'
import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import ResultFixtureCard from '@/components/ResultFixtureCard.vue'
import {
  favoriteToListFixture,
  type FavoriteFixtureRecord,
} from '@/composables/useFavoriteFixtures'
import CalcFixtureCard from '@/views/Predictions/components/CalcFixtureCard.vue'
import { useIsPhone } from '@/composables/useMediaQuery'
import { isFixtureCardMarkClickIgnored } from '@/utils/fixtureCardMark'

const props = withDefaults(
  defineProps<{
    item: FavoriteFixtureRecord
    selectable?: boolean
    selected?: boolean
    activeLeagueId?: number | null
  }>(),
  {
    selectable: false,
    selected: false,
    activeLeagueId: undefined,
  },
)

const emit = defineEmits<{
  openDetail: [fixtureId: number]
  toggleSelect: [fixtureId: number]
  selectLeague: [leagueId: number | null]
}>()

const isPhone = useIsPhone()
const showOddsModal = ref(false)

const listFixture = computed(() => favoriteToListFixture(props.item))

/** Any settled fixture uses the same card as the results list. */
const isFinished = computed(() => {
  const status = (props.item.status || '').toLowerCase()
  if (status === 'finished') return true
  return props.item.home_goals != null && props.item.away_goals != null
})

const desktopMarkClass = computed(() => ({
  'fa-card-markable': props.selectable,
  'is-marked': props.selected,
}))

function openDetail() {
  emit('openDetail', props.item.fixture_id)
}

function openOddsModal() {
  showOddsModal.value = true
}

/** Desktop outer card owns the mark; phone ResultFixtureCard handles it. */
function onDesktopMarkClick(e: MouseEvent) {
  if (!props.selectable) return
  if (isFixtureCardMarkClickIgnored(e)) return
  emit('toggleSelect', props.item.fixture_id)
}
</script>

<template>
  <ResultFixtureCard
    v-if="isFinished && isPhone"
    :fixture="item"
    odds-clickable
    :selectable="selectable"
    :selected="selected"
    @open-detail="openDetail"
    @open-odds="openOddsModal"
    @toggle-select="emit('toggleSelect', $event)"
  />

  <div
    v-else-if="isFinished"
    class="favorite-fixture-card"
    :class="desktopMarkClass"
    @click="onDesktopMarkClick"
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
  </div>

  <div
    v-else
    class="favorite-prematch"
    :class="[desktopMarkClass, { phone: isPhone }]"
    @click="onDesktopMarkClick"
  >
    <CalcFixtureCard
      v-if="isPhone"
      :fixture="listFixture"
      from="favorites"
    />
    <div v-else class="fixture-row">
      <div class="fixture-row-pred">
        <AlgorithmPredictionCard
          :fixture="listFixture"
          standalone
          from="favorites"
          :active-league-id="activeLeagueId"
          @select-league="emit('selectLeague', $event)"
        />
      </div>
      <div class="fixture-row-calc">
        <CalcFixtureCard :fixture="listFixture" from="favorites" />
      </div>
    </div>
  </div>

  <PreMatchOddsModal
    v-if="isPhone"
    v-model:show="showOddsModal"
    :odds="item.odds_snippet"
    :fixture-id="item.fixture_id"
    from="favorites"
  />
</template>

<style scoped>
.favorite-fixture-card {
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

.favorite-prematch {
  min-width: 0;
  max-width: 100%;
}

.favorite-prematch.phone {
  height: 184px;
  overflow: hidden;
}

.favorite-prematch.phone > :deep(*) {
  height: 100%;
}

.fixture-row {
  display: grid;
  grid-template-columns: minmax(0, 5.5fr) minmax(0, 4.5fr);
  gap: 5px;
  height: 147px;
  min-width: 0;
  overflow: hidden;
}

.fixture-row-pred,
.fixture-row-calc {
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.fixture-row-pred > :deep(*),
.fixture-row-calc > :deep(*) {
  height: 100%;
}
</style>
