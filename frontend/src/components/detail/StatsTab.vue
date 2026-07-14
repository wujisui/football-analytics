<script setup lang="ts">
import { computed } from 'vue'

import { useMediaQuery } from '@/composables/useMediaQuery'
import type { FixtureResponse, FormMatch, FormPackage, PrematchPackage } from '@/api/types'
import { toPercent } from '@/utils/format'
import { teamNameZh } from '@/utils/teamNames'

const props = defineProps<{
  fixture: FixtureResponse
  pkg: PrematchPackage | null
}>()

function parseGoals(score: string): [number, number] | null {
  const m = score.trim().match(/^(\d+)\s*[-:]\s*(\d+)$/)
  if (!m) return null
  return [Number(m[1]), Number(m[2])]
}

function winRate(form: FormPackage | undefined): number | null {
  if (!form || form.played <= 0) return null
  return form.wins / form.played
}

function teamGoalAvgs(
  teamName: string,
  matches: FormMatch[],
): { scored: number | null; conceded: number | null } {
  let scored = 0
  let conceded = 0
  let n = 0
  for (const m of matches) {
    const g = parseGoals(m.score)
    if (!g) continue
    const home = m.home.trim()
    const away = m.away.trim()
    if (home === teamName || home.includes(teamName) || teamName.includes(home)) {
      scored += g[0]
      conceded += g[1]
      n += 1
    } else if (away === teamName || away.includes(teamName) || teamName.includes(away)) {
      scored += g[1]
      conceded += g[0]
      n += 1
    }
  }
  if (!n) return { scored: null, conceded: null }
  return { scored: scored / n, conceded: conceded / n }
}

const isStatsNarrow = useMediaQuery('(max-width: 720px)')
const statsCols = computed(() => (isStatsNarrow.value ? 1 : 2))

const homeWinRate = computed(() => winRate(props.pkg?.home_form))
const awayWinRate = computed(() => winRate(props.pkg?.away_form))

const homeGoals = computed(() =>
  teamGoalAvgs(props.fixture.home_team_name, props.pkg?.home_form.matches ?? []),
)
const awayGoals = computed(() =>
  teamGoalAvgs(props.fixture.away_team_name, props.pkg?.away_form.matches ?? []),
)

const hasAny = computed(
  () =>
    homeWinRate.value != null ||
    awayWinRate.value != null ||
    homeGoals.value.scored != null ||
    awayGoals.value.scored != null,
)

function fmtAvg(n: number | null): string {
  if (n == null) return '—'
  return n.toFixed(1)
}

function pctLabel(n: number | null): string {
  if (n == null) return '—'
  return toPercent(n)
}
</script>

<template>
  <n-space vertical :size="14">
    <template v-if="hasAny">
      <n-grid :cols="statsCols" :x-gap="14" :y-gap="14">
        <n-gi>
          <n-card size="small" :title="teamNameZh(fixture.home_team_name, fixture.home_team_id)">
            <n-space vertical :size="14">
              <div>
                <n-statistic label="近况胜率" :value="pctLabel(homeWinRate)" />
                <n-progress
                  v-if="homeWinRate != null"
                  type="line"
                  :percentage="Math.round(homeWinRate * 100)"
                  :show-indicator="false"
                  status="success"
                  style="margin-top: 6px"
                />
              </div>
              <n-statistic label="场均进球（近况）" :value="fmtAvg(homeGoals.scored)" />
              <n-statistic label="场均失球（近况）" :value="fmtAvg(homeGoals.conceded)" />
            </n-space>
          </n-card>
        </n-gi>
        <n-gi>
          <n-card size="small" :title="teamNameZh(fixture.away_team_name, fixture.away_team_id)">
            <n-space vertical :size="14">
              <div>
                <n-statistic label="近况胜率" :value="pctLabel(awayWinRate)" />
                <n-progress
                  v-if="awayWinRate != null"
                  type="line"
                  :percentage="Math.round(awayWinRate * 100)"
                  :show-indicator="false"
                  style="margin-top: 6px"
                />
              </div>
              <n-statistic label="场均进球（近况）" :value="fmtAvg(awayGoals.scored)" />
              <n-statistic label="场均失球（近况）" :value="fmtAvg(awayGoals.conceded)" />
            </n-space>
          </n-card>
        </n-gi>
      </n-grid>

      <n-card v-if="pkg?.standings?.available" size="small" title="本赛事排名">
        <n-text>
          主 {{ pkg.standings.home_rank ?? '—' }} /
          客 {{ pkg.standings.away_rank ?? '—' }}
          <template v-if="pkg.standings.group">（{{ pkg.standings.group }}）</template>
        </n-text>
      </n-card>
    </template>
    <n-empty v-else description="暂无可用统计数据" />
  </n-space>
</template>
