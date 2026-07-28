<script setup lang="ts">
import { computed } from 'vue'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FavoriteButton from '@/components/FavoriteButton.vue'
import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import type { FixtureResponse } from '@/api/types'
import { useIsPhone } from '@/composables/useMediaQuery'
import {
  formatDate,
  formatTime,
  leagueTagColor,
  statusLabel,
  statusTagType,
} from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'
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
  <article class="fixture-card" :class="{ 'phone-compact': isPhone }">
    <header class="card-head">
      <n-tag
        size="small"
        :bordered="false"
        :color="{
          color: `${leagueTagColor(fixture.league_id)}18`,
          textColor: leagueTagColor(fixture.league_id),
        }"
      >
        {{ leagueLabel(fixture.league_name) }}
      </n-tag>
      <span class="kickoff">
        {{ formatDate(fixture.fixture_date) }} {{ formatTime(fixture.fixture_date) }}
      </span>
      <n-tag size="small" :type="statusTagType(fixture.status)" :bordered="false">
        {{ statusLabel(fixture.status) }}
      </n-tag>
      <FavoriteButton
        :fixture-id="fixture.fixture_id"
        :fixture="fixture"
        size="tiny"
      />
    </header>

    <div class="summary-grid" :class="{ 'predict-only': isPhone }">
      <PreMatchOddsTable
        v-if="!isPhone"
        :odds="fixture.odds_snippet"
        :home-name="homeName"
        :away-name="awayName"
        link-middle-to-detail
        :fixture-id="fixture.fixture_id"
        :from="from"
        :date="date"
        detail-tab="record"
      />
      <AlgorithmPredictionCard
        :fixture="fixture"
        link-to-detail
        :from="from"
        :date="date"
      />
    </div>
  </article>
</template>

<style scoped>
.fixture-card {
  background: var(--fa-bg-elevated);
  border: 1px solid var(--fa-border);
  border-radius: 8px;
  padding: 16px;
  cursor: default;
  user-select: text;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
  display: flex;
  flex-direction: column;
  gap: 10px;
  color: var(--fa-text);
}

.fixture-card:hover {
  border-color: var(--fa-hover-border);
  box-shadow: 0 2px 10px var(--fa-hover-shadow);
}

.card-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.kickoff {
  font-size: 13px;
  color: var(--fa-text-secondary);
  flex: 1;
}

.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: start;
}

.summary-grid.predict-only {
  grid-template-columns: 1fr;
}

@media (max-width: 900px) {
  .summary-grid:not(.predict-only) {
    grid-template-columns: 1fr;
  }

  .fixture-card {
    padding: 12px;
  }
}

@media (max-width: 767px) {
  .phone-compact .card-head {
    gap: 6px;
  }
}
</style>
