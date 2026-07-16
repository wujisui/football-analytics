<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import AlgorithmPredictionCard from '@/components/AlgorithmPredictionCard.vue'
import type { FixtureResponse } from '@/api/types'
import { useIsPhone } from '@/composables/useMediaQuery'
import {
  formatDate,
  formatOdd,
  formatTime,
  leagueTagColor,
  rankBracket,
  statusLabel,
  statusTagType,
} from '@/utils/format'
import { leagueNameZh } from '@/utils/leagueNames'
import { FIXTURE_DETAIL_TOOLTIP } from '@/utils/detailNav'

const props = defineProps<{
  fixture: FixtureResponse
}>()

const router = useRouter()
const isPhone = useIsPhone()

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

/** Main AH line (backend already sorts even-money first). */
const ahMain = computed(() => ahLines.value[0] ?? null)
const ahExtraCount = computed(() => Math.max(0, ahLines.value.length - 1))

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

function goDetail() {
  router.push({
    name: 'fixture-detail',
    params: { fixtureId: props.fixture.fixture_id },
    query: { from: 'home' },
  })
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
    </header>

    <div v-if="!isPhone" class="matchup">
      <span class="team home">{{ homeLabel }}</span>
      <n-tooltip placement="top">
        <template #trigger>
          <button
            type="button"
            class="vs"
            :aria-label="FIXTURE_DETAIL_TOOLTIP"
            @click="goDetail"
          >
            VS
          </button>
        </template>
        {{ FIXTURE_DETAIL_TOOLTIP }}
      </n-tooltip>
      <span class="team away">{{ awayLabel }}</span>
    </div>

    <div class="summary-grid" :class="{ 'predict-only': isPhone }">
      <section v-if="!isPhone" class="zone odds-zone">
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
            <div v-if="ahMain" class="market-row">
              <span class="market-label">
                让球
                <span v-if="ahExtraCount > 0" class="ah-more">+{{ ahExtraCount }}</span>
              </span>
              <span class="market-col">{{ formatOdd(ahMain.home) }}</span>
              <span class="market-col mid line">
                <n-popover
                  v-if="ahExtraCount > 0"
                  trigger="hover"
                  placement="bottom"
                  :show-arrow="false"
                  :delay="120"
                  raw
                >
                  <template #trigger>
                    <span
                      class="ah-line-trigger"
                      tabindex="0"
                      role="button"
                      :aria-label="`主盘 ${ahMain.line}，另有 ${ahExtraCount} 条让球盘`"
                    >
                      {{ ahMain.line || '—' }}
                    </span>
                  </template>
                  <div class="fixture-ah-popover">
                    <div class="market-row market-head">
                      <span class="market-label">让球</span>
                      <span class="market-col">{{ homeName }}</span>
                      <span class="market-col mid">盘口</span>
                      <span class="market-col">{{ awayName }}</span>
                    </div>
                    <div
                      v-for="(row, idx) in ahLines"
                      :key="`ah-pop-${row.line}-${idx}`"
                      class="market-row"
                    >
                      <span class="market-label" />
                      <span class="market-col">{{ formatOdd(row.home) }}</span>
                      <span class="market-col mid line">{{ row.line || '—' }}</span>
                      <span class="market-col">{{ formatOdd(row.away) }}</span>
                    </div>
                  </div>
                </n-popover>
                <template v-else>{{ ahMain.line || '—' }}</template>
              </span>
              <span class="market-col">{{ formatOdd(ahMain.away) }}</span>
            </div>
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

.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: stretch;
}

.summary-grid.predict-only {
  grid-template-columns: 1fr;
}

.zone {
  background: var(--fa-bg-soft);
  border-radius: 6px;
  padding: 12px;
  min-width: 0;
  height: 100%;
  box-sizing: border-box;
}

.odds-zone {
  display: flex;
  flex-direction: column;
}

.zone-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--fa-text-secondary);
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

.ah-line-trigger {
  display: inline-block;
  min-width: 100%;
  cursor: default;
  border-radius: 3px;
  outline: none;
  text-decoration: underline;
  text-decoration-style: dotted;
  text-underline-offset: 3px;
}

.ah-line-trigger:hover,
.ah-line-trigger:focus-visible {
  background: var(--fa-bg-elevated);
}

.ah-more {
  margin-left: 2px;
  font-size: 10px;
  font-weight: 600;
  color: var(--fa-accent, #2080f0);
  vertical-align: middle;
}

.odds-empty {
  margin: 0;
  font-size: 12px;
  color: var(--fa-text-faint);
  line-height: 1.5;
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

<!-- Popover content is teleported; keep class names unique to this feature. -->
<style>
.fixture-ah-popover {
  min-width: 280px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--fa-border);
  background: var(--fa-bg-elevated);
  box-shadow: 0 8px 24px var(--fa-hover-shadow);
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--fa-text-secondary);
}

.fixture-ah-popover .market-row {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) 52px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}

.fixture-ah-popover .market-head {
  margin-bottom: 2px;
  color: var(--fa-text-faint);
  font-size: 11px;
}

.fixture-ah-popover .market-label {
  text-align: left;
  color: var(--fa-text-faint);
}

.fixture-ah-popover .market-col {
  text-align: center;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--fa-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fixture-ah-popover .market-col.mid {
  color: var(--fa-text-secondary);
}

.fixture-ah-popover .market-col.line {
  font-weight: 700;
  color: var(--fa-accent, #2080f0);
}

.fixture-ah-popover .market-head .market-col {
  font-weight: 500;
  color: var(--fa-text-faint);
}
</style>
