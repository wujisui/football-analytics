<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import type { FixtureResponse } from '@/api/types'
import {
  formatDateTime,
  leagueTagColor,
  rankBracket,
  statusLabel,
  statusTagType,
} from '@/utils/format'
import { teamNameZh } from '@/utils/teamNames'
import { leagueNameZh } from '@/utils/leagueNames'

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
      <n-breadcrumb-item @click="goLeague">{{ leagueNameZh(fixture.league_name) }}</n-breadcrumb-item>
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
            {{ leagueNameZh(fixture.league_name) }}
          </n-tag>
          <n-tag size="small" :type="statusTagType(fixture.status)" :bordered="false">
            {{ statusLabel(fixture.status) }}
          </n-tag>
          <span class="kickoff">{{ formatDateTime(fixture.fixture_date) }}</span>
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

:deep(.n-breadcrumb-item .n-breadcrumb-item__link) {
  cursor: pointer;
}

:deep(.n-breadcrumb-item:last-child .n-breadcrumb-item__link) {
  cursor: default;
}
</style>
