<script setup lang="ts">
import { ArrowBackOutline } from '@vicons/ionicons5'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { FixtureResponse } from '@/api/types'
import { rankBracket } from '@/utils/format'
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

function goBack() {
  if (from.value === 'favorites' && window.history.length > 1) {
    void router.back()
    return
  }
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
    <div class="header-row">
      <n-button
        class="back-btn"
        quaternary
        circle
        size="small"
        aria-label="返回"
        @click="goBack"
      >
        <template #icon>
          <n-icon :component="ArrowBackOutline" />
        </template>
      </n-button>

      <n-breadcrumb class="header-crumb">
        <n-breadcrumb-item @click="goBack">{{ rootLabel }}</n-breadcrumb-item>
        <n-breadcrumb-item @click="goLeague">{{ leagueLabelText }}</n-breadcrumb-item>
        <n-breadcrumb-item>
          <n-tooltip v-if="scoreText" placement="bottom">
            <template #trigger>
              <span class="match-title crumb-match">
                <span>{{ homeLabel }}</span>
                <span class="score-value">{{ scoreText }}</span>
                <span>{{ awayLabel }}</span>
              </span>
            </template>
            本地比分（非实时）
          </n-tooltip>
          <span v-else class="match-title crumb-match">
            <span>{{ homeLabel }}</span>
            <span>VS</span>
            <span>{{ awayLabel }}</span>
          </span>
        </n-breadcrumb-item>
      </n-breadcrumb>
    </div>
  </div>
</template>

<style scoped>
.basic-info {
  background: var(--fa-bg-elevated);
  border: 1px solid var(--fa-border);
  border-radius: 8px;
  padding: 10px 12px;
}

.header-row {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.back-btn {
  flex-shrink: 0;
}

.header-crumb {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.crumb-match {
  font-variant-numeric: tabular-nums;
}

.match-title {
  display: inline-flex;
  align-items: baseline;
  gap: 0.45em;
  min-width: 0;
}

.score-value {
  flex-shrink: 0;
  color: var(--fa-highlight-text);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

:deep(.n-breadcrumb-item .n-breadcrumb-item__link) {
  cursor: pointer;
}

:deep(.n-breadcrumb-item:last-child .n-breadcrumb-item__link) {
  cursor: default;
}
</style>
