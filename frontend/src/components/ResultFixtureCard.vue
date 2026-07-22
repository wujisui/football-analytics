<script setup lang="ts">
import { computed } from 'vue'

import type { ResultFixture } from '@/api/fixtures'
import FavoriteButton from '@/components/FavoriteButton.vue'
import ResultHitTags from '@/components/ResultHitTags.vue'
import {
  formatDate,
  formatTime,
  leagueTagColor,
  statusLabel,
  statusTagType,
} from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'
import {
  resultExtraScoreLine,
  resultScoreText,
} from '@/utils/resultsDisplay'

const props = defineProps<{
  fixture: ResultFixture
}>()

const emit = defineEmits<{
  openDetail: [fixtureId: number]
}>()

const homeName = computed(() => props.fixture.home_team_name || '—')
const awayName = computed(() => props.fixture.away_team_name || '—')
const scoreText = computed(() => resultScoreText(props.fixture))
const extraScoreLine = computed(() => resultExtraScoreLine(props.fixture))

function statusTag(
  status: string,
  statusShort?: string | null,
): ReturnType<typeof statusTagType> {
  if (status.toLowerCase() === 'finished') return 'error'
  return statusTagType(status, statusShort)
}

function openDetail() {
  emit('openDetail', props.fixture.fixture_id)
}
</script>

<template>
  <article class="result-fixture-card">
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
      <n-tag
        size="small"
        :type="statusTag(fixture.status, fixture.status_short)"
        :bordered="false"
      >
        {{ statusLabel(fixture.status, fixture.status_short) }}
      </n-tag>
      <FavoriteButton
        :fixture-id="fixture.fixture_id"
        :result-fixture="fixture"
        size="tiny"
      />
    </header>

    <div class="matchup">
      <span class="team home">{{ homeName }}</span>
      <button
        type="button"
        class="score-btn"
        :aria-label="`查看 ${homeName} 对 ${awayName} 详情`"
        @click="openDetail"
      >
        {{ scoreText }}
      </button>
      <span class="team away">{{ awayName }}</span>
    </div>
    <p v-if="extraScoreLine" class="score-extra">{{ extraScoreLine }}</p>

    <template v-if="fixture.has_prediction">
      <n-text depth="3" class="pred-line">
        {{ fixture.recommendation || '—' }}
        · {{ fixture.score_hint || '—' }}
        · {{ fixture.goal_lean || '—' }}
        · {{ fixture.both_score_lean || '—' }}
      </n-text>
      <ResultHitTags :fixture="fixture" />
    </template>
    <n-text v-else depth="3" class="no-pred">无赛前预测</n-text>
  </article>
</template>

<style scoped>
.result-fixture-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  background: var(--fa-bg-soft);
}

.card-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.kickoff {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: var(--fa-text-secondary);
}

.matchup {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-weight: 600;
}

.team {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.team.home {
  text-align: right;
}

.team.away {
  text-align: left;
}

.score-btn {
  appearance: none;
  margin: 0;
  padding: 0;
  border: none;
  background: none;
  color: var(--fa-text-strong);
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  cursor: pointer;
  flex-shrink: 0;
}

.score-btn:hover {
  color: var(--fa-highlight-text);
}

.score-btn:focus-visible {
  outline: 2px solid var(--fa-highlight-border);
  outline-offset: 2px;
  border-radius: 2px;
}

.score-extra {
  margin: -4px 0 0;
  text-align: center;
  font-size: 11px;
  color: var(--fa-text-secondary);
}

.pred-line {
  display: block;
  font-size: 11px;
  line-height: 1.45;
}

.no-pred {
  font-size: 11px;
}
</style>
