<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import type { FixtureResponse } from '@/api/types'
import {
  formatDateTime,
  formatOdd,
  leagueTagColor,
  rankBracket,
  statusLabel,
  statusTagType,
} from '@/utils/format'
import { teamNameZh } from '@/utils/teamNames'

const props = defineProps<{
  fixture: FixtureResponse
}>()

const router = useRouter()

const homeName = computed(() =>
  teamNameZh(props.fixture.home_team_name, props.fixture.home_team_id),
)
const awayName = computed(() =>
  teamNameZh(props.fixture.away_team_name, props.fixture.away_team_id),
)

const matchTitle = computed(() => {
  const hr = rankBracket(props.fixture.home_rank)
  const ar = rankBracket(props.fixture.away_rank)
  const home = hr ? `${hr} ${homeName.value}` : homeName.value
  const away = ar ? `${awayName.value} ${ar}` : awayName.value
  return `${home} VS ${away}`
})

const odds = computed(() => props.fixture.odds_snippet)
const ah = computed(() => odds.value?.asian_handicap ?? null)
const ou = computed(() => odds.value?.goals_ou ?? null)
const mw = computed(() => odds.value?.match_winner ?? null)

function goHome() {
  router.push({ name: 'home' })
}

function goLeague() {
  router.push({
    name: 'home',
    query: { league: String(props.fixture.league_id) },
  })
}
</script>

<template>
  <div class="basic-info">
    <n-breadcrumb>
      <n-breadcrumb-item @click="goHome">赛前赛事</n-breadcrumb-item>
      <n-breadcrumb-item @click="goLeague">{{ fixture.league_name }}</n-breadcrumb-item>
      <n-breadcrumb-item>{{ matchTitle }}</n-breadcrumb-item>
    </n-breadcrumb>

    <n-page-header :title="matchTitle" @back="goHome">
      <template #subtitle>
        <div class="subtitle-row">
          <n-tag
            size="small"
            :bordered="false"
            :color="{
              color: `${leagueTagColor(fixture.league_id)}18`,
              textColor: leagueTagColor(fixture.league_id),
            }"
          >
            {{ fixture.league_name }}
          </n-tag>
          <n-tag size="small" :type="statusTagType(fixture.status)" :bordered="false">
            {{ statusLabel(fixture.status) }}
          </n-tag>
          <span class="kickoff">{{ formatDateTime(fixture.fixture_date) }}</span>
        </div>
        <p v-if="fixture.home_rank != null || fixture.away_rank != null" class="rank-hint">
          排名为本赛事积分榜位置（如欧协联小组/联赛阶段），不是各自国内联赛排名
        </p>
        <div v-if="mw || ah || ou" class="odds-strip">
          <span v-if="mw" class="odds-item">
            胜平负 {{ formatOdd(mw.home) }} / {{ formatOdd(mw.draw) }} / {{ formatOdd(mw.away) }}
          </span>
          <span v-if="ah" class="odds-item">
            让球 <em>{{ ah.line || '—' }}</em>
            {{ formatOdd(ah.home) }} / {{ formatOdd(ah.away) }}
          </span>
          <span v-if="ou" class="odds-item">
            大小 <em>{{ ou.line || '—' }}</em>
            {{ formatOdd(ou.home) }} / {{ formatOdd(ou.away) }}
          </span>
        </div>
      </template>
    </n-page-header>
  </div>
</template>

<style scoped>
.basic-info {
  background: var(--fa-bg-elevated);
  border: 1px solid var(--fa-border);
  border-radius: 8px;
  padding: 14px 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.subtitle-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.kickoff {
  font-size: 13px;
  color: var(--fa-text-secondary);
}

.rank-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--fa-text-faint);
}

.odds-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 18px;
  margin-top: 8px;
  font-size: 13px;
  color: var(--fa-text-secondary);
}

.odds-item em {
  font-style: normal;
  font-weight: 700;
  color: var(--fa-accent, #2080f0);
  margin: 0 4px;
}

:deep(.n-breadcrumb-item .n-breadcrumb-item__link) {
  cursor: pointer;
}

:deep(.n-breadcrumb-item:last-child .n-breadcrumb-item__link) {
  cursor: default;
}
</style>
