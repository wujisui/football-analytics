<script setup lang="ts">
import { computed } from 'vue'

import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import ResultFixtureCard from '@/components/ResultFixtureCard.vue'
import type { FixtureResponse } from '@/api/types'
import { useIsPhone } from '@/composables/useMediaQuery'
import type { DetailFrom } from '@/utils/detailNav'

const props = withDefaults(
  defineProps<{
    fixture: FixtureResponse
    from?: DetailFrom
    date?: string | null
  }>(),
  {
    from: 'home',
    date: null,
  },
)

const isPhone = useIsPhone()

const homeName = computed(() => props.fixture.home_team_name || '—')
const awayName = computed(() => props.fixture.away_team_name || '—')
</script>

<template>
  <ResultFixtureCard
    v-if="isPhone"
    :fixture="fixture"
    :from="from"
    :date="date"
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
        :home-name="homeName"
        :away-name="awayName"
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
