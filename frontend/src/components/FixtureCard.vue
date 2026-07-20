<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FavoriteButton from '@/components/FavoriteButton.vue'
import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import type { FixtureResponse } from '@/api/types'
import { useIsPhone } from '@/composables/useMediaQuery'
import {
  formatDate,
  formatTime,
  leagueTagColor,
  rankBracket,
  statusLabel,
  statusTagType,
} from '@/utils/format'
import { leagueNameZh } from '@/utils/leagueNames'
import { FIXTURE_DETAIL_TOOLTIP, fixtureDetailRoute } from '@/utils/detailNav'

const props = defineProps<{
  fixture: FixtureResponse
}>()

const router = useRouter()
const isPhone = useIsPhone()

const homeName = computed(() => props.fixture.home_team_name || '—')
const awayName = computed(() => props.fixture.away_team_name || '—')

const homeLabel = computed(() => {
  const rank = rankBracket(props.fixture.home_rank)
  return rank ? `${rank} ${homeName.value}` : homeName.value
})

const awayLabel = computed(() => {
  const rank = rankBracket(props.fixture.away_rank)
  return rank ? `${awayName.value} ${rank}` : awayName.value
})

const scoreText = computed(() => {
  const h = props.fixture.home_goals
  const a = props.fixture.away_goals
  if (h == null || a == null) return null
  return `${h}:${a}`
})

function goDetail() {
  void router.push(fixtureDetailRoute(props.fixture.fixture_id, { from: 'home' }))
}
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
        {{ leagueNameZh(fixture.league_name, { leagueId: fixture.league_id }) }}
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

    <div v-if="!isPhone" class="matchup">
      <span class="team home">{{ homeLabel }}</span>
      <n-tooltip placement="top">
        <template #trigger>
          <button
            type="button"
            class="vs"
            :class="{ score: scoreText }"
            :aria-label="FIXTURE_DETAIL_TOOLTIP"
            @click="goDetail"
          >
            {{ scoreText ?? 'VS' }}
          </button>
        </template>
        {{ FIXTURE_DETAIL_TOOLTIP }}
      </n-tooltip>
      <span class="team away">{{ awayLabel }}</span>
    </div>

    <div v-else class="matchup phone-matchup">
      <span class="team home">{{ homeLabel }}</span>
      <button
        type="button"
        class="vs"
        :class="{ score: scoreText }"
        :aria-label="FIXTURE_DETAIL_TOOLTIP"
        @click="goDetail"
      >
        {{ scoreText ?? 'VS' }}
      </button>
      <span class="team away">{{ awayLabel }}</span>
    </div>

    <div class="summary-grid" :class="{ 'predict-only': isPhone }">
      <PreMatchOddsTable v-if="!isPhone"
          :odds="fixture.odds_snippet"
          :home-name="homeName"
          :away-name="awayName"
          link-middle-to-detail
          :fixture-id="fixture.fixture_id"
          from="home"
          detail-tab="prediction"
        />
      <AlgorithmPredictionCard :fixture="fixture" :link-to-detail="isPhone" />
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
  gap: 12px;
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

.matchup {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 2px 0;
}

.team {
  font-size: 16px;
  font-weight: 600;
  color: var(--fa-text-strong);
  text-align: center;
  flex: 1;
}

.vs {
  appearance: none;
  margin: 0;
  padding: 0;
  border: none;
  background: none;
  color: var(--fa-text-strong);
  font: inherit;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.06em;
  line-height: 1;
  cursor: pointer;
  flex-shrink: 0;
  transition: color 0.15s ease;
}

.vs:hover {
  color: var(--fa-highlight-text);
}

.vs:focus-visible {
  outline: 2px solid var(--fa-highlight-border);
  outline-offset: 2px;
  border-radius: 2px;
}

.vs.score {
  font-size: 18px;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}

.phone-matchup {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 2px 0;
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
    gap: 10px;
  }

  .matchup {
    gap: 8px;
  }

  .team {
    font-size: 14px;
  }
}

@media (max-width: 767px) {
  .phone-compact .card-head {
    gap: 6px;
  }

  .phone-compact .kickoff {
    flex: 1 1 auto;
  }
}
</style>
