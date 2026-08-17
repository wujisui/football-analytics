<script setup lang="ts">
import { ref } from 'vue'

import PreMatchOddsModal from '@/components/PreMatchOddsModal.vue'
import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import ResultFixtureCard from '@/components/ResultFixtureCard.vue'
import type { FixtureResponse } from '@/api/types'
import { useIsPhone } from '@/composables/useMediaQuery'
import type { DetailFrom } from '@/utils/detailNav'

withDefaults(
  defineProps<{
    fixture: FixtureResponse
    from?: DetailFrom
    date?: string | null
  }>(),
  {
    from: 'predictions',
    date: null,
  },
)

const isPhone = useIsPhone()
const showOddsModal = ref(false)
</script>

<template>
  <ResultFixtureCard
    v-if="isPhone"
    :fixture="fixture"
    odds-clickable
    :from="from"
    :date="date"
    @open-odds="showOddsModal = true"
  />

  <n-card
    v-else
    size="small"
    :bordered="false"
    style="background: var(--fa-bg-elevated);"
  >
    <div class="summary-grid">
      <PreMatchOddsTable
        :odds="fixture.odds_snippet"
        link-middle-to-detail
        :fixture-id="fixture.fixture_id"
        :from="from"
        :date="date"
      />
      <ResultFixtureCard
        :fixture="fixture"
        :from="from"
        :date="date"
      />
    </div>
  </n-card>

  <PreMatchOddsModal
    v-if="isPhone"
    v-model:show="showOddsModal"
    :odds="fixture.odds_snippet"
    :fixture-id="fixture.fixture_id"
    :from="from"
    :date="date"
  />
</template>

<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: stretch;
}

.summary-grid :deep(.result-fixture-card) {
  height: 100%;
}

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
