<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import type { FixtureResponse } from '@/api/types'
import {
  formatDate,
  formatOdd,
  formatTime,
  hasRealProbabilities,
  leagueTagColor,
  rankBracket,
  statusLabel,
  statusTagType,
  toPercent,
} from '@/utils/format'
import { snapshotFromAnalysis } from '@/utils/opinionAdjust'
import { leagueNameZh } from '@/utils/leagueNames'
import { teamNameZh } from '@/utils/teamNames'

const props = defineProps<{
  fixture: FixtureResponse
}>()

const router = useRouter()

const prediction = computed(() => snapshotFromAnalysis(props.fixture.analysis))
const predictionReady = computed(() =>
  hasRealProbabilities(
    props.fixture.analysis.probabilities,
    prediction.value.recommendation,
  ),
)
const recommendationPending = computed(
  () => !predictionReady.value || prediction.value.recommendation === '待分析',
)
const handicapPending = computed(() => {
  const text = prediction.value.handicap_lean || ''
  return !text || text.includes('缺少盘口') || text.includes('待分析')
})

const odds = computed(() => props.fixture.odds_snippet)
const ah = computed(() => odds.value?.asian_handicap ?? null)
const ou = computed(() => odds.value?.goals_ou ?? null)
const mw = computed(() => odds.value?.match_winner ?? null)
const hasMarkets = computed(() => !!(mw.value || ah.value || ou.value))

const ahLines = computed(() => {
  const market = ah.value
  if (!market) return []
  if (market.lines?.length) {
    return market.lines.filter((l) => l.line != null && l.line !== '')
  }
  if (market.line != null && market.line !== '') {
    return [{ line: market.line, home: market.home, away: market.away }]
  }
  return []
})

const homeName = computed(() =>
  teamNameZh(props.fixture.home_team_name, props.fixture.home_team_id),
)
const awayName = computed(() =>
  teamNameZh(props.fixture.away_team_name, props.fixture.away_team_id),
)

const homeLabel = computed(() => {
  const rank = rankBracket(props.fixture.home_rank)
  return rank ? `${rank} ${homeName.value}` : homeName.value
})

const awayLabel = computed(() => {
  const rank = rankBracket(props.fixture.away_rank)
  return rank ? `${awayName.value} ${rank}` : awayName.value
})

const probs = computed(() => {
  if (!predictionReady.value) return []
  return [
    { key: 'home', label: '主胜', value: prediction.value.home_win_prob },
    { key: 'draw', label: '平局', value: prediction.value.draw_prob },
    { key: 'away', label: '客胜', value: prediction.value.away_win_prob },
  ]
})

function goDetail() {
  router.push({
    name: 'fixture-detail',
    params: { fixtureId: props.fixture.fixture_id },
  })
}
</script>

<template>
  <article class="fixture-card">
    <header class="card-head">
      <n-tag
        size="small"
        :bordered="false"
        :color="{
          color: `${leagueTagColor(fixture.league_id)}18`,
          textColor: leagueTagColor(fixture.league_id),
        }"
      >
        {{ leagueNameZh(fixture.league_name) }}
      </n-tag>
      <span class="kickoff">
        {{ formatDate(fixture.fixture_date) }} {{ formatTime(fixture.fixture_date) }}
      </span>
      <n-tag size="small" :type="statusTagType(fixture.status)" :bordered="false">
        {{ statusLabel(fixture.status) }}
      </n-tag>
    </header>

    <div class="matchup">
      <span class="team home">{{ homeLabel }}</span>
      <button
        type="button"
        class="vs"
        title="查看详细分析"
        aria-label="查看详细分析"
        @click="goDetail"
      >
        VS
      </button>
      <span class="team away">{{ awayLabel }}</span>
    </div>

    <div class="summary-grid">
      <section class="zone odds-zone">
        <h3 class="zone-title">赛前盘口</h3>
        <template v-if="hasMarkets">
          <div class="markets">
            <div class="market-row market-head">
              <span class="market-label" />
              <span class="market-col">{{ homeName }}</span>
              <span class="market-col mid">vs</span>
              <span class="market-col">{{ awayName }}</span>
            </div>
            <div v-if="mw" class="market-row">
              <span class="market-label">胜平负</span>
              <span class="market-col">{{ formatOdd(mw.home) }}</span>
              <span class="market-col mid">{{ formatOdd(mw.draw) }}</span>
              <span class="market-col">{{ formatOdd(mw.away) }}</span>
            </div>
            <template v-if="ahLines.length">
              <div
                v-for="(row, idx) in ahLines"
                :key="`ah-${row.line}-${idx}`"
                class="market-row"
              >
                <span class="market-label">{{ idx === 0 ? '让球' : '' }}</span>
                <span class="market-col">{{ formatOdd(row.home) }}</span>
                <span class="market-col mid line">{{ row.line || '—' }}</span>
                <span class="market-col">{{ formatOdd(row.away) }}</span>
              </div>
            </template>
            <div v-if="ou" class="market-row">
              <span class="market-label">大小</span>
              <span class="market-col">{{ formatOdd(ou.home) }}</span>
              <span class="market-col mid line">{{ ou.line || '—' }}</span>
              <span class="market-col">{{ formatOdd(ou.away) }}</span>
            </div>
          </div>
        </template>
        <p v-else class="odds-empty">暂无盘口（打开详情拉取后显示）</p>
      </section>

      <section class="zone predict-zone">
        <h3 class="zone-title">算法预测</h3>
        <div class="rec-row">
          <span class="rec-label">推荐</span>
          <n-tag
            :type="recommendationPending ? 'default' : 'primary'"
            size="small"
          >
            {{ prediction.recommendation }}
          </n-tag>
          <n-tag
            :type="handicapPending ? 'default' : 'warning'"
            size="small"
            class="rec-tag"
          >
            {{ prediction.handicap_lean || '缺少盘口数据分析' }}
          </n-tag>
        </div>
        <div v-if="predictionReady" class="prob-row">
          <div v-for="p in probs" :key="p.key" class="prob-item">
            <span class="prob-label">{{ p.label }}</span>
            <span class="prob-value">{{ toPercent(p.value) }}</span>
            <n-progress
              type="line"
              :percentage="Math.round(p.value * 100)"
              :show-indicator="false"
              :height="6"
              processing
            />
          </div>
        </div>
        <p v-else class="predict-empty">暂无有效胜平负概率（缺近况或盘口）</p>
        <div v-if="predictionReady" class="lean-row">
          <n-tag size="small" :bordered="false">{{ prediction.goal_lean }}</n-tag>
          <n-tag size="small" :bordered="false">{{ prediction.both_score_lean }}</n-tag>
          <n-tag size="small" :bordered="false" type="info">
            参考比分 {{ prediction.score_hint }}
          </n-tag>
        </div>
        <div v-else-if="!handicapPending" class="lean-row">
          <n-tag size="small" :bordered="false" type="warning">
            {{ prediction.handicap_lean }}
          </n-tag>
        </div>
      </section>
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
  border: 1px solid var(--fa-hover-border);
  background: var(--fa-bg-soft);
  color: var(--fa-text-strong);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  line-height: 1;
  padding: 8px 12px;
  border-radius: 999px;
  cursor: pointer;
  flex-shrink: 0;
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-thickness: 1.5px;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.vs:hover {
  background: var(--fa-highlight-bg);
  border-color: var(--fa-highlight-border);
  color: var(--fa-highlight-text);
  box-shadow: 0 1px 6px var(--fa-hover-shadow);
}

.vs:active {
  transform: scale(0.96);
}

.vs:focus-visible {
  outline: 2px solid var(--fa-highlight-border);
  outline-offset: 2px;
}

.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.zone {
  background: var(--fa-bg-soft);
  border-radius: 6px;
  padding: 12px;
  min-width: 0;
}

.zone-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--fa-text-secondary);
}

.rec-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.rec-label {
  font-size: 13px;
  color: var(--fa-text-secondary);
  flex-shrink: 0;
}

.rec-tag {
  max-width: 100%;
  white-space: normal;
  height: auto;
  line-height: 1.4;
  padding: 2px 8px;
}

.prob-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.prob-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.prob-label {
  font-size: 12px;
  color: var(--fa-text-faint);
}

.prob-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--fa-text-strong);
  font-variant-numeric: tabular-nums;
}

.lean-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.predict-empty {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--fa-text-faint);
}

.markets {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--fa-text-secondary);
}

.market-row {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) 52px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}

.market-head {
  margin-bottom: 2px;
  color: var(--fa-text-faint);
  font-size: 11px;
}

.market-label {
  text-align: left;
  color: var(--fa-text-faint);
}

.market-col {
  text-align: center;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--fa-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.market-col.mid {
  color: var(--fa-text-secondary);
}

.market-col.line {
  font-weight: 700;
  color: var(--fa-accent, #2080f0);
}

.market-head .market-col {
  font-weight: 500;
  color: var(--fa-text-faint);
}

.odds-empty {
  margin: 0;
  font-size: 12px;
  color: var(--fa-text-faint);
  line-height: 1.5;
}

@media (max-width: 900px) {
  .summary-grid {
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

  .market-head .market-col {
    font-size: 11px;
  }

  .lean-row {
    gap: 6px;
  }
}

@media (max-width: 480px) {
  .card-head {
    gap: 6px;
  }

  .kickoff {
    flex: 1 1 100%;
    order: 3;
  }
}
</style>
