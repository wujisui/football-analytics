<script setup lang="ts">
import {ChevronBackOutline} from '@vicons/ionicons5'
import {computed} from 'vue'
import {useRoute, useRouter} from 'vue-router'

import {
  detailBackRoute,
  detailRootLabel,
  parseDetailFrom,
  type DetailCrumbFixture,
} from '@/utils/detailNav'
import {useIsPhone} from '@/composables/useMediaQuery'
import {writeFixturesLeagueFilter} from '@/utils/fixturesLeagueFilter'
import {rankBracket} from '@/utils/format'
import {leagueLabel} from '@/utils/leagueNames'

const props = defineProps<{
  fixture: DetailCrumbFixture | null
}>()

const route = useRoute()
const router = useRouter()
const isPhone = useIsPhone()

const from = computed(() => parseDetailFrom(route.query.from))
const fromDate = computed(() =>
    typeof route.query.date === 'string' ? route.query.date : null,
)
const rootLabel = computed(() => detailRootLabel(from.value))
const leagueLabelText = computed(() =>
    props.fixture?.league_name ? leagueLabel(props.fixture.league_name) : '',
)

const scoreText = computed(() => {
  const h = props.fixture?.home_goals
  const a = props.fixture?.away_goals
  if (h == null || a == null) return null
  return `${h}:${a}`
})

const homeLabel = computed(() => {
  if (!props.fixture) return '—'
  const hr = rankBracket(props.fixture.home_rank)
  const homeName = props.fixture.home_team_name || '—'
  return hr ? `${hr} ${homeName}` : homeName
})

const awayLabel = computed(() => {
  if (!props.fixture) return '—'
  const ar = rankBracket(props.fixture.away_rank)
  const awayName = props.fixture.away_team_name || '—'
  return ar ? `${awayName} ${ar}` : awayName
})

function goBack() {
  void router.push(
      detailBackRoute(from.value, {
        date: fromDate.value,
      }),
  )
}

function goLeague() {
  if (!props.fixture?.league_id) {
    goBack()
    return
  }
  if (from.value !== 'predictions') {
    goBack()
    return
  }
  writeFixturesLeagueFilter(props.fixture.league_id, 'prematch')
  void router.push(
      detailBackRoute('predictions', {leagueId: props.fixture.league_id}),
  )
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
          <n-icon :component="ChevronBackOutline"/>
        </template>
      </n-button>

      <n-breadcrumb class="header-crumb">
        <n-breadcrumb-item v-if="!isPhone" @click="goBack">
          {{ rootLabel }}
        </n-breadcrumb-item>
        <n-breadcrumb-item
            v-if="!isPhone && leagueLabelText"
            @click="goLeague"
        >
          {{ leagueLabelText }}
        </n-breadcrumb-item>
        <n-breadcrumb-item v-if="fixture">
           <span v-if="scoreText" class="match-title crumb-match">
                <span>{{ homeLabel }}</span>
                <span class="score-value">{{ scoreText }}</span>
                <span>{{ awayLabel }}</span>
              </span>
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
