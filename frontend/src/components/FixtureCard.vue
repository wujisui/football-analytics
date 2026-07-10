<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import type { FixtureResponse } from '@/api/types'
import {
  analysisConclusion,
  confidenceType,
  formatDate,
  formatOdd,
  formatTime,
  leagueTagColor,
  rankBracket,
  statusLabel,
  statusTagType,
  toPercent,
} from '@/utils/format'
import { teamNameZh } from '@/utils/teamNames'

const props = defineProps<{
  fixture: FixtureResponse
}>()

const router = useRouter()

const conclusion = computed(() =>
  analysisConclusion(
    props.fixture.analysis.recommendation,
    props.fixture.analysis.probabilities,
  ),
)

const probs = computed(() => props.fixture.analysis.probabilities)
const odds = computed(() => props.fixture.odds_snippet)
const ah = computed(() => odds.value?.asian_handicap ?? null)
const ou = computed(() => odds.value?.goals_ou ?? null)
const mw = computed(() => odds.value?.match_winner ?? null)

const homeLabel = computed(() => {
  const name = teamNameZh(props.fixture.home_team_name, props.fixture.home_team_id)
  const rank = rankBracket(props.fixture.home_rank)
  return rank ? `${rank} ${name}` : name
})

const awayLabel = computed(() => {
  const name = teamNameZh(props.fixture.away_team_name, props.fixture.away_team_id)
  const rank = rankBracket(props.fixture.away_rank)
  return rank ? `${name} ${rank}` : name
})

const headlineLine = computed(() => {
  if (ah.value?.line) return ah.value.line
  if (ou.value?.line) return ou.value.line
  return ''
})

const hasMarkets = computed(
  () => !!(mw.value || ah.value || ou.value),
)

function goDetail() {
  router.push({
    name: 'fixture-detail',
    params: { fixtureId: props.fixture.fixture_id },
  })
}
</script>

<template>
  <article class="fixture-card" role="button" tabindex="0" @click="goDetail" @keydown.enter="goDetail">
    <header class="card-head">
      <n-tag
        size="small"
        :bordered="false"
        :color="{ color: `${leagueTagColor(fixture.league_id)}18`, textColor: leagueTagColor(fixture.league_id) }"
      >
        {{ fixture.league_name }}
      </n-tag>
      <span class="kickoff">
        {{ formatDate(fixture.fixture_date) }} {{ formatTime(fixture.fixture_date) }}
      </span>
      <span v-if="headlineLine" class="headline-line">{{ headlineLine }}</span>
      <n-tag size="small" :type="statusTagType(fixture.status)" :bordered="false">
        {{ statusLabel(fixture.status) }}
      </n-tag>
    </header>

    <div class="matchup">
      <span class="team home">{{ homeLabel }}</span>
      <span class="vs">VS</span>
      <span class="team away">{{ awayLabel }}</span>
    </div>

    <div v-if="hasMarkets" class="markets">
      <div v-if="mw" class="market-row">
        <span class="market-label">胜平负</span>
        <span>{{ formatOdd(mw.home) }}</span>
        <span class="line">{{ formatOdd(mw.draw) }}</span>
        <span>{{ formatOdd(mw.away) }}</span>
      </div>
      <div v-if="ah" class="market-row">
        <span class="market-label">让球</span>
        <span>{{ formatOdd(ah.home) }}</span>
        <span class="line">{{ ah.line || '—' }}</span>
        <span>{{ formatOdd(ah.away) }}</span>
      </div>
      <div v-if="ou" class="market-row">
        <span class="market-label">大小</span>
        <span>{{ formatOdd(ou.home) }}</span>
        <span class="line">{{ ou.line || '—' }}</span>
        <span>{{ formatOdd(ou.away) }}</span>
      </div>
    </div>

    <p class="conclusion">分析结论：{{ conclusion }}</p>

    <div class="meta-row">
      <n-tag size="small" type="primary" :bordered="false">
        {{ fixture.analysis.recommendation }}
      </n-tag>
      <n-tag
        size="small"
        :type="confidenceType(fixture.analysis.confidence)"
        :bordered="false"
      >
        置信度 {{ fixture.analysis.confidence }}
      </n-tag>
      <span class="prob-text">
        主 {{ toPercent(probs.home_win_prob) }} /
        平 {{ toPercent(probs.draw_prob) }} /
        客 {{ toPercent(probs.away_win_prob) }}
      </span>
    </div>

    <footer class="card-foot">
      <n-button type="primary" ghost size="small" @click.stop="goDetail">
        查看详细分析
      </n-button>
    </footer>
  </article>
</template>

<style scoped>
.fixture-card {
  background: var(--fa-bg-elevated);
  border: 1px solid var(--fa-border);
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
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

.headline-line {
  font-size: 13px;
  font-weight: 700;
  color: var(--fa-accent, #2080f0);
}

.matchup {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 4px 0;
}

.team {
  font-size: 16px;
  font-weight: 600;
  color: var(--fa-text-strong);
  text-align: center;
  flex: 1;
}

.vs {
  font-size: 12px;
  font-weight: 700;
  color: var(--fa-text-faint);
  letter-spacing: 0.04em;
}

.markets {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px;
  background: var(--fa-bg-soft);
  border-radius: 6px;
  font-size: 12px;
  color: var(--fa-text-secondary);
}

.market-row {
  display: grid;
  grid-template-columns: 48px 1fr auto 1fr;
  gap: 8px;
  align-items: center;
  text-align: center;
}

.market-label {
  text-align: left;
  color: var(--fa-text-faint);
}

.line {
  font-weight: 700;
  color: var(--fa-accent, #2080f0);
  min-width: 48px;
}

.conclusion {
  margin: 0;
  font-size: 14px;
  color: var(--fa-text);
  line-height: 1.5;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.prob-text {
  font-size: 12px;
  color: var(--fa-text-muted);
}

.card-foot {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
  border-top: 1px solid var(--fa-border-soft);
}
</style>
