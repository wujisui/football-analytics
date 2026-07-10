<script setup lang="ts">
import { computed, ref } from 'vue'

import type { FormMatch, PrematchPackage } from '@/api/types'
import {
  formCharClass,
  formCharsZh,
  formatDateShort,
  resultTagType,
  resultToZh,
} from '@/utils/format'
import { leagueNameZh } from '@/utils/leagueNames'
import { teamNameZh } from '@/utils/teamNames'

const props = defineProps<{
  homeTeamName: string
  awayTeamName: string
  homeTeamId?: number
  awayTeamId?: number
  pkg: PrematchPackage | null
}>()

/** Display count only — backend stores up to 20; free plan may return fewer. */
const displayLimit = ref(5)
const limitOptions = [
  { label: '近 5 场', value: 5 },
  { label: '近 8 场', value: 8 },
  { label: '近 10 场', value: 10 },
  { label: '近 15 场', value: 15 },
  { label: '近 20 场', value: 20 },
]

const homeZh = computed(() => teamNameZh(props.homeTeamName, props.homeTeamId))
const awayZh = computed(() => teamNameZh(props.awayTeamName, props.awayTeamId))

const h2h = computed(() => props.pkg?.head_to_head ?? null)
const h2hMatches = computed(
  () => h2h.value?.matches?.slice(0, displayLimit.value) ?? [],
)
const h2hSummary = computed(() => {
  const matches = h2hMatches.value
  return {
    played: matches.length,
    home_wins: matches.filter((m) => m.outcome_for_current_home === 'home').length,
    draws: matches.filter((m) => m.outcome_for_current_home === 'draw').length,
    away_wins: matches.filter((m) => m.outcome_for_current_home === 'away').length,
  }
})
const homeForm = computed(() => props.pkg?.home_form ?? null)
const awayForm = computed(() => props.pkg?.away_form ?? null)
const homeRecent = computed(
  () => homeForm.value?.matches?.slice(0, displayLimit.value) ?? [],
)
const awayRecent = computed(
  () => awayForm.value?.matches?.slice(0, displayLimit.value) ?? [],
)

function formSliceSummary(matches: FormMatch[]) {
  return {
    wins: matches.filter((m) => m.result === 'W').length,
    draws: matches.filter((m) => m.result === 'D').length,
    losses: matches.filter((m) => m.result === 'L').length,
  }
}

const homeSliceSummary = computed(() => formSliceSummary(homeRecent.value))
const awaySliceSummary = computed(() => formSliceSummary(awayRecent.value))

const hasAny = computed(
  () =>
    (h2h.value?.played ?? 0) > 0 ||
    (homeForm.value?.matches?.length ?? 0) > 0 ||
    (awayForm.value?.matches?.length ?? 0) > 0,
)

function competitionLabel(m: FormMatch): string {
  return leagueNameZh(m.league_name)
}

function h2hResultLabel(m: FormMatch): string {
  const o = m.outcome_for_current_home
  if (o === 'home') return '主胜'
  if (o === 'away') return '客胜'
  if (o === 'draw') return '平'
  return resultToZh(m.result)
}

function h2hResultType(m: FormMatch): 'success' | 'warning' | 'error' | 'default' {
  const label = h2hResultLabel(m)
  if (label === '主胜') return 'success'
  if (label === '平') return 'warning'
  if (label === '客胜') return 'error'
  return resultTagType(m.result)
}
</script>

<template>
  <div class="h2h-tab">
    <n-empty
      v-if="!hasAny"
      description="暂无交战与近期战绩（免费套餐历史赛季约 2022–2024）"
    />

    <template v-else>
      <div class="toolbar">
        <span class="toolbar-label">展示场次</span>
        <n-select
          v-model:value="displayLimit"
          size="small"
          :options="limitOptions"
          :consistent-menu-width="false"
          style="width: 120px"
        />
        <span class="hint inline">
          后端最多存 20 场；交锋窗口约 2022–2024（免费套餐）
        </span>
      </div>

      <section class="block">
        <h3 class="block-title">双方交锋</h3>
        <template v-if="h2h && h2h.played > 0">
          <div class="summary-bar">
            近 {{ h2hSummary.played }} 次（库内 {{ h2h.played }}）：
            <strong>{{ homeZh }}</strong>
            {{ h2hSummary.home_wins }} 胜 /
            {{ h2hSummary.draws }} 平 /
            <strong>{{ awayZh }}</strong>
            {{ h2hSummary.away_wins }} 胜
          </div>
          <ul class="list">
            <li
              v-for="(m, idx) in h2hMatches"
              :key="`h2h-${m.fixture_id ?? idx}`"
              class="row"
              :class="{ latest: idx === 0 }"
            >
              <span class="date">{{ formatDateShort(m.date || '') }}</span>
              <n-tag v-if="competitionLabel(m)" size="tiny" :bordered="false" type="info">
                {{ competitionLabel(m) }}
              </n-tag>
              <span class="teams">
                {{ teamNameZh(m.home) }} vs {{ teamNameZh(m.away) }}
              </span>
              <span class="score">{{ m.score }}</span>
              <n-tag size="tiny" :type="h2hResultType(m)" :bordered="false">
                {{ h2hResultLabel(m) }}
              </n-tag>
              <n-tag v-if="idx === 0" size="tiny" type="info" :bordered="false">最近</n-tag>
            </li>
          </ul>
        </template>
        <n-empty v-else description="双方暂无直接交锋记录，下方展示各自近期对阵" size="small" />
      </section>

      <div class="split">
        <section class="block">
          <h3 class="block-title">{{ homeZh }} · 近期战绩</h3>
          <div v-if="homeForm?.form" class="badges">
            <span
              v-for="(zh, i) in formCharsZh(homeForm.form, displayLimit)"
              :key="i"
              class="badge"
              :class="formCharClass(zh)"
            >
              {{ zh }}
            </span>
          </div>
          <p v-if="homeRecent.length" class="summary">
            {{ homeSliceSummary.wins }}胜 {{ homeSliceSummary.draws }}平
            {{ homeSliceSummary.losses }}负 · 展示 {{ homeRecent.length }} /
            {{ homeForm?.played ?? 0 }}
          </p>
          <ul v-if="homeRecent.length" class="list">
            <li
              v-for="(m, idx) in homeRecent"
              :key="`hf-${m.fixture_id ?? idx}`"
              class="row"
            >
              <span class="date">{{ formatDateShort(m.date || '') }}</span>
              <n-tag v-if="competitionLabel(m)" size="tiny" :bordered="false" type="info">
                {{ competitionLabel(m) }}
              </n-tag>
              <span class="teams">
                {{ teamNameZh(m.home) }} vs {{ teamNameZh(m.away) }}
              </span>
              <span class="score">{{ m.score }}</span>
              <n-tag size="tiny" :type="resultTagType(m.result)" :bordered="false">
                {{ resultToZh(m.result) }}
              </n-tag>
            </li>
          </ul>
          <n-empty v-else description="暂无近期赛果" size="small" />
        </section>

        <section class="block">
          <h3 class="block-title">{{ awayZh }} · 近期战绩</h3>
          <div v-if="awayForm?.form" class="badges">
            <span
              v-for="(zh, i) in formCharsZh(awayForm.form, displayLimit)"
              :key="i"
              class="badge"
              :class="formCharClass(zh)"
            >
              {{ zh }}
            </span>
          </div>
          <p v-if="awayRecent.length" class="summary">
            {{ awaySliceSummary.wins }}胜 {{ awaySliceSummary.draws }}平
            {{ awaySliceSummary.losses }}负 · 展示 {{ awayRecent.length }} /
            {{ awayForm?.played ?? 0 }}
          </p>
          <ul v-if="awayRecent.length" class="list">
            <li
              v-for="(m, idx) in awayRecent"
              :key="`af-${m.fixture_id ?? idx}`"
              class="row"
            >
              <span class="date">{{ formatDateShort(m.date || '') }}</span>
              <n-tag v-if="competitionLabel(m)" size="tiny" :bordered="false" type="info">
                {{ competitionLabel(m) }}
              </n-tag>
              <span class="teams">
                {{ teamNameZh(m.home) }} vs {{ teamNameZh(m.away) }}
              </span>
              <span class="score">{{ m.score }}</span>
              <n-tag size="tiny" :type="resultTagType(m.result)" :bordered="false">
                {{ resultToZh(m.result) }}
              </n-tag>
            </li>
          </ul>
          <n-empty v-else description="暂无近期赛果" size="small" />
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.h2h-tab {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.toolbar-label {
  font-size: 13px;
  color: var(--fa-text-secondary);
}

.block-title {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 700;
}

.hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--fa-text-faint);
}

.hint.inline {
  margin: 0;
}

.summary-bar {
  padding: 12px 14px;
  background: var(--fa-bg-soft);
  border-radius: 6px;
  font-size: 14px;
  color: var(--fa-text);
  line-height: 1.5;
  margin-bottom: 10px;
}

.badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.badge {
  min-width: 26px;
  height: 26px;
  padding: 0 6px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: #999;
}

.badge.w {
  background: #18a058;
}

.badge.d {
  background: #909399;
}

.badge.l {
  background: #d03050;
}

.summary {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--fa-text-secondary);
}

.split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--fa-border);
  border-radius: 6px;
  background: var(--fa-bg-elevated);
  font-size: 13px;
}

.row.latest {
  border-color: var(--fa-highlight-border);
  background: var(--fa-highlight-bg);
}

.date {
  color: var(--fa-text-faint);
  min-width: 96px;
}

.teams {
  flex: 1;
  min-width: 140px;
}

.score {
  font-weight: 700;
  min-width: 40px;
}

@media (max-width: 900px) {
  .split {
    grid-template-columns: 1fr;
  }
}
</style>
