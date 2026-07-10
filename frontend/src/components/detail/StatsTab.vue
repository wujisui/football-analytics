<script setup lang="ts">
import { computed } from 'vue'

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
  <div class="stats-tab">
    <p class="hint">
      以下指标由近况场次估算（后端暂无独立赛季统计接口）。完整主客场赛季数据待后续接入。
    </p>

    <template v-if="hasAny">
      <div class="grid">
        <n-card size="small" :title="teamNameZh(fixture.home_team_name, fixture.home_team_id)">
          <div class="metric">
            <div class="label">近况胜率</div>
            <div class="value">{{ pctLabel(homeWinRate) }}</div>
            <n-progress
              v-if="homeWinRate != null"
              type="line"
              :percentage="Math.round(homeWinRate * 100)"
              :show-indicator="false"
              status="success"
            />
          </div>
          <div class="metric">
            <div class="label">场均进球（近况）</div>
            <div class="value">{{ fmtAvg(homeGoals.scored) }}</div>
          </div>
          <div class="metric">
            <div class="label">场均失球（近况）</div>
            <div class="value">{{ fmtAvg(homeGoals.conceded) }}</div>
          </div>
        </n-card>

        <n-card size="small" :title="teamNameZh(fixture.away_team_name, fixture.away_team_id)">
          <div class="metric">
            <div class="label">近况胜率</div>
            <div class="value">{{ pctLabel(awayWinRate) }}</div>
            <n-progress
              v-if="awayWinRate != null"
              type="line"
              :percentage="Math.round(awayWinRate * 100)"
              :show-indicator="false"
            />
          </div>
          <div class="metric">
            <div class="label">场均进球（近况）</div>
            <div class="value">{{ fmtAvg(awayGoals.scored) }}</div>
          </div>
          <div class="metric">
            <div class="label">场均失球（近况）</div>
            <div class="value">{{ fmtAvg(awayGoals.conceded) }}</div>
          </div>
        </n-card>
      </div>

      <n-card v-if="pkg?.odds.available" size="small" title="赛前盘口参考">
        <n-descriptions v-if="pkg.odds.match_winner" :column="3" size="small">
          <n-descriptions-item label="主胜">
            {{ pkg.odds.match_winner.home ?? '—' }}
          </n-descriptions-item>
          <n-descriptions-item label="平局">
            {{ pkg.odds.match_winner.draw ?? '—' }}
          </n-descriptions-item>
          <n-descriptions-item label="客胜">
            {{ pkg.odds.match_winner.away ?? '—' }}
          </n-descriptions-item>
        </n-descriptions>
        <n-descriptions
          v-if="pkg.odds.asian_handicap"
          :column="3"
          size="small"
          style="margin-top: 10px"
        >
          <n-descriptions-item label="让球盘">
            {{ pkg.odds.asian_handicap.line ?? '—' }}
          </n-descriptions-item>
          <n-descriptions-item label="主队水位">
            {{ pkg.odds.asian_handicap.home ?? '—' }}
          </n-descriptions-item>
          <n-descriptions-item label="客队水位">
            {{ pkg.odds.asian_handicap.away ?? '—' }}
          </n-descriptions-item>
        </n-descriptions>
        <n-descriptions
          v-if="pkg.odds.goals_ou"
          :column="3"
          size="small"
          style="margin-top: 10px"
        >
          <n-descriptions-item label="大小球">
            {{ pkg.odds.goals_ou.line ?? '—' }}
          </n-descriptions-item>
          <n-descriptions-item label="大球">
            {{ pkg.odds.goals_ou.home ?? '—' }}
          </n-descriptions-item>
          <n-descriptions-item label="小球">
            {{ pkg.odds.goals_ou.away ?? '—' }}
          </n-descriptions-item>
        </n-descriptions>
        <p v-if="pkg.standings?.available" class="hint" style="margin-top: 10px">
          本赛事排名：主 {{ pkg.standings.home_rank ?? '—' }} /
          客 {{ pkg.standings.away_rank ?? '—' }}
          <template v-if="pkg.standings.group">（{{ pkg.standings.group }}）</template>
        </p>
      </n-card>
    </template>
    <n-empty v-else description="暂无可用统计数据" />
  </div>
</template>

<style scoped>
.stats-tab {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.hint {
  margin: 0;
  font-size: 12px;
  color: var(--fa-text-faint);
  line-height: 1.5;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.metric {
  margin-bottom: 14px;
}

.metric:last-child {
  margin-bottom: 0;
}

.label {
  font-size: 12px;
  color: var(--fa-text-muted);
  margin-bottom: 4px;
}

.value {
  font-size: 22px;
  font-weight: 700;
  color: var(--fa-text-strong);
  margin-bottom: 6px;
}

@media (max-width: 720px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
