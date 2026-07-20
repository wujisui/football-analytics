<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import FavoriteButton from '@/components/FavoriteButton.vue'
import type { FixtureResponse } from '@/api/types'
import {
  formatDateTime,
  leagueTagColor,
  rankBracket,
  statusLabel,
  statusTagType,
} from '@/utils/format'
import {
  detailBackRoute,
  detailRootLabel,
  parseDetailFrom,
} from '@/utils/detailNav'
import { writeFixturesLeagueFilter } from '@/utils/fixturesLeagueFilter'
import { leagueLabel } from '@/utils/leagueNames'

const props = defineProps<{
  fixture: FixtureResponse
}>()

const route = useRoute()
const router = useRouter()

const from = computed(() => parseDetailFrom(route.query.from))
const fromDate = computed(() =>
  typeof route.query.date === 'string' ? route.query.date : null,
)
const rootLabel = computed(() => detailRootLabel(from.value))

const leagueLabelText = computed(() => leagueLabel(props.fixture.league_name))

const scoreText = computed(() => {
  const h = props.fixture.home_goals
  const a = props.fixture.away_goals
  if (h == null || a == null) return null
  return `${h}:${a}`
})

const homeLabel = computed(() => {
  const hr = rankBracket(props.fixture.home_rank)
  const homeName = props.fixture.home_team_name || '—'
  return hr ? `${hr} ${homeName}` : homeName
})

const awayLabel = computed(() => {
  const ar = rankBracket(props.fixture.away_rank)
  const awayName = props.fixture.away_team_name || '—'
  return ar ? `${awayName} ${ar}` : awayName
})

/** Breadcrumb / title: show local score between teams when available. */
const matchTitle = computed(() => {
  if (scoreText.value) {
    return `${homeLabel.value} ${scoreText.value} ${awayLabel.value}`
  }
  return `${homeLabel.value} VS ${awayLabel.value}`
})

function goBack() {
  void router.push(
    detailBackRoute(from.value, {
      date: fromDate.value,
    }),
  )
}

function goLeague() {
  if (from.value !== 'home') {
    goBack()
    return
  }
  writeFixturesLeagueFilter(props.fixture.league_id, 'prematch')
  void router.push(detailBackRoute('home', { leagueId: props.fixture.league_id }))
}
</script>

<template>
  <div class="basic-info">
    <n-breadcrumb>
      <n-breadcrumb-item @click="goBack">{{ rootLabel }}</n-breadcrumb-item>
      <n-breadcrumb-item @click="goLeague">{{ leagueLabelText }}</n-breadcrumb-item>
      <n-breadcrumb-item>
        <n-tooltip v-if="scoreText" placement="bottom">
          <template #trigger>
            <span class="crumb-match">{{ matchTitle }}</span>
          </template>
          本地比分（非实时）
        </n-tooltip>
        <span v-else class="crumb-match">{{ matchTitle }}</span>
      </n-breadcrumb-item>
    </n-breadcrumb>

    <n-page-header :title="matchTitle" @back="goBack">
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
            {{ leagueLabelText }}
          </n-tag>
          <n-tag size="small" :type="statusTagType(fixture.status)" :bordered="false">
            {{ statusLabel(fixture.status) }}
          </n-tag>
          <span class="kickoff">{{ formatDateTime(fixture.fixture_date) }}</span>
        </div>
      </template>
      <template #extra>
        <FavoriteButton :fixture-id="fixture.fixture_id" :fixture="fixture" />
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

.crumb-match {
  font-variant-numeric: tabular-nums;
}

:deep(.n-breadcrumb-item .n-breadcrumb-item__link) {
  cursor: pointer;
}

:deep(.n-breadcrumb-item:last-child .n-breadcrumb-item__link) {
  cursor: default;
}
</style>
