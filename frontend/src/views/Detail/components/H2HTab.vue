<script setup lang="ts">
import { computed, ref } from 'vue'

import MatchStatsSummary from '@/views/Detail/components/MatchStatsSummary.vue'
import MatchStatsTable from '@/views/Detail/components/MatchStatsTable.vue'
import { useMediaQuery } from '@/composables/useMediaQuery'
import type { FixtureResponse, FormMatch, PrematchPackage } from '@/api/types'
import { formCharClass, formCharsZh, hasKickedOff } from '@/utils/format'
import { primaryAhLine } from '@/utils/oddsDisplay'

const props = defineProps<{
  fixture: FixtureResponse
  pkg: PrematchPackage | null
}>()

/** Match former CSS: 1fr 1fr above 900px, stack below. */
const isFormNarrow = useMediaQuery('(max-width: 900px)')
const formCols = computed(() => (isFormNarrow.value ? 1 : 2))

const h2hLimit = ref(10)
const formLimit = ref(10)
const limitOptions = [
  { label: '近 5 场', value: 5 },
  { label: '近 8 场', value: 8 },
  { label: '近 10 场', value: 10 },
  { label: '近 15 场', value: 15 },
  { label: '近 20 场', value: 20 },
]

const homeZh = computed(() => props.fixture.home_team_name || '—')
const awayZh = computed(() => props.fixture.away_team_name || '—')

const h2hMatches = computed(
  () => props.pkg?.head_to_head?.matches?.slice(0, h2hLimit.value) ?? [],
)
const currentMatch = computed<FormMatch | null>(() => {
  if (hasKickedOff(props.fixture.fixture_date)) return null
  return {
    fixture_id: props.fixture.fixture_id,
    date: props.fixture.fixture_date,
    status: 'pending',
    home: props.fixture.home_team_name,
    away: props.fixture.away_team_name,
    home_id: props.fixture.home_team_id,
    away_id: props.fixture.away_team_id,
    score: 'VS',
    league_id: props.fixture.league_id,
    league_name: props.fixture.league_name,
    league_country: props.fixture.league_country,
    ah_opening: primaryAhLine(props.pkg?.odds_opening ?? null),
    ah_current: primaryAhLine(props.pkg?.odds ?? null),
  }
})
const displayedH2HMatches = computed(() =>
  currentMatch.value ? [currentMatch.value, ...h2hMatches.value] : h2hMatches.value,
)
const homeRecent = computed(
  () => props.pkg?.home_form?.matches?.slice(0, formLimit.value) ?? [],
)
const awayRecent = computed(
  () => props.pkg?.away_form?.matches?.slice(0, formLimit.value) ?? [],
)
const homeForm = computed(() => props.pkg?.home_form ?? null)
const awayForm = computed(() => props.pkg?.away_form ?? null)

const hasAny = computed(
  () =>
    currentMatch.value != null ||
    (props.pkg?.head_to_head?.matches?.length ?? 0) > 0 ||
    (props.pkg?.home_form?.matches?.length ?? 0) > 0 ||
    (props.pkg?.away_form?.matches?.length ?? 0) > 0,
)
</script>

<template>
  <n-empty v-if="!hasAny" description="暂无交战与近期战绩" />

  <n-space v-else vertical :size="12">
    <n-space vertical :size="12">
      <n-flex class="section-band" justify="space-between" align="center" :size="12">
        <n-flex align="center" :size="8">
          <span class="title-bar" aria-hidden="true" />
          <n-text strong style="font-size: 15px">历史交锋</n-text>
        </n-flex>
        <n-flex align="center" :size="8">
          <n-text depth="3" style="font-size: 13px; white-space: nowrap">展示场次</n-text>
          <n-select
            v-model:value="h2hLimit"
            size="small"
            :options="limitOptions"
            :consistent-menu-width="false"
            style="width: 120px"
          />
        </n-flex>
      </n-flex>
      <MatchStatsSummary
        :matches="h2hMatches"
        :focus-team-id="fixture.home_team_id"
      />
      <MatchStatsTable
        :matches="displayedH2HMatches"
        :focus-team-id="fixture.home_team_id"
        empty-description="双方暂无直接交锋记录"
        show-odds
      />
    </n-space>

    <n-flex class="section-band" justify="space-between" align="center" :size="12">
      <n-flex align="center" :size="8">
        <span class="title-bar" aria-hidden="true" />
        <n-text strong style="font-size: 15px">近期战绩</n-text>
      </n-flex>
      <n-flex align="center" :size="8">
        <n-text depth="3" style="font-size: 13px; white-space: nowrap">展示场次</n-text>
        <n-select
          v-model:value="formLimit"
          size="small"
          :options="limitOptions"
          :consistent-menu-width="false"
          style="width: 120px"
        />
      </n-flex>
    </n-flex>

    <n-grid :cols="formCols" :x-gap="16" :y-gap="16">
      <n-gi>
        <n-space vertical :size="8">
          <n-text strong>{{ homeZh }}</n-text>
          <n-flex v-if="homeForm?.form" class="badges" :size="6" :wrap="false">
            <span
              v-for="(zh, i) in formCharsZh(homeForm.form, formLimit)"
              :key="i"
              class="badge"
              :class="formCharClass(zh)"
            >
              {{ zh }}
            </span>
          </n-flex>
          <MatchStatsSummary
            :matches="homeRecent"
            :focus-team-id="fixture.home_team_id"
          />
          <MatchStatsTable
            :matches="homeRecent"
            :focus-team-id="fixture.home_team_id"
          />
        </n-space>
      </n-gi>
      <n-gi>
        <n-space vertical :size="8">
          <n-text strong>{{ awayZh }}</n-text>
          <n-flex v-if="awayForm?.form" class="badges" :size="6" :wrap="false">
            <span
              v-for="(zh, i) in formCharsZh(awayForm.form, formLimit)"
              :key="i"
              class="badge"
              :class="formCharClass(zh)"
            >
              {{ zh }}
            </span>
          </n-flex>
          <MatchStatsSummary
            :matches="awayRecent"
            :focus-team-id="fixture.away_team_id"
          />
          <MatchStatsTable
            :matches="awayRecent"
            :focus-team-id="fixture.away_team_id"
          />
        </n-space>
      </n-gi>
    </n-grid>
  </n-space>
</template>

<style scoped>
.section-band {
  padding: 10px 12px;
  background: var(--fa-bg-soft);
}

.title-bar {
  width: 3px;
  height: 14px;
  border-radius: 1px;
  background: var(--fa-wdl-win);
  flex-shrink: 0;
}

/* W/D/L chips — business viz (allowed outside Naive). */
.badges {
  overflow-x: auto;
  padding-bottom: 2px;
}

.badge {
  min-width: 26px;
  width: 26px;
  height: 26px;
  border-radius: var(--fa-radius-card);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: var(--fa-wdl-draw);
  flex-shrink: 0;
}

.badge.w {
  background: var(--fa-wdl-win);
}

.badge.d {
  background: var(--fa-wdl-draw);
}

.badge.l {
  background: var(--fa-wdl-loss);
}
</style>
