<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import FavoriteButton from '@/components/FavoriteButton.vue'
import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import ScoreDetailLink from '@/components/ScoreDetailLink.vue'
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
import { leagueLabel } from '@/utils/leagueNames'
import { fixtureDetailRoute, type DetailFrom } from '@/utils/detailNav'

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
  void router.push(
    fixtureDetailRoute(props.fixture.fixture_id, {
      from: props.from,
      date: props.date,
    }),
  )
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

    <div class="matchup" :class="{ 'phone-matchup': isPhone }">
      <span class="team home">{{ homeLabel }}</span>
      <ScoreDetailLink
        class="vs"
        :class="{ score: scoreText }"
        :label="scoreText ?? 'VS'"
        @click="goDetail"
      />
      <span class="team away">{{ awayLabel }}</span>
    </div>

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
        detail-tab="prediction"
      />
      <AlgorithmPredictionCard
        :fixture="fixture"
        :link-to-detail="isPhone"
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
  gap: 3px;
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
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.vs.score {
  font-size: 18px;
  letter-spacing: 0;
}

.phone-matchup {
  gap: 8px;
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
}
</style>
