<script setup lang="ts">
import { computed } from 'vue'

import type { FormMatch } from '@/api/types'

const props = defineProps<{
  matches: FormMatch[]
  focusTeamId?: number
}>()

function parseScore(score: string): [number, number] | null {
  const m = String(score).match(/^(\d+)\s*-\s*(\d+)$/)
  if (!m) return null
  return [Number(m[1]), Number(m[2])]
}

function resultForFocus(m: FormMatch, focusTeamId?: number): 'W' | 'D' | 'L' | '' {
  const goals = parseScore(m.score || '')
  if (focusTeamId != null && m.home_id != null && m.away_id != null && goals) {
    const [hs, as] = goals
    const hid = Number(m.home_id)
    const aid = Number(m.away_id)
    if (hid === focusTeamId) {
      if (hs > as) return 'W'
      if (hs < as) return 'L'
      return 'D'
    }
    if (aid === focusTeamId) {
      if (as > hs) return 'W'
      if (as < hs) return 'L'
      return 'D'
    }
  }
  if (m.result === 'W' || m.result === 'D' || m.result === 'L') return m.result
  if (m.outcome_for_current_home === 'home') return 'W'
  if (m.outcome_for_current_home === 'away') return 'L'
  if (m.outcome_for_current_home === 'draw') return 'D'
  return ''
}

function goalsForFocus(
  m: FormMatch,
  focusTeamId?: number,
): { gf: number; ga: number } | null {
  const goals = parseScore(m.score || '')
  if (!goals) return null
  const [hs, as] = goals
  if (focusTeamId != null && m.home_id != null && m.away_id != null) {
    if (Number(m.home_id) === focusTeamId) return { gf: hs, ga: as }
    if (Number(m.away_id) === focusTeamId) return { gf: as, ga: hs }
  }
  return { gf: hs, ga: as }
}

function formatAvg(n: number): string {
  if (!Number.isFinite(n)) return '0'
  const rounded = Math.round(n * 10) / 10
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1)
}

const stats = computed(() => {
  const matches = props.matches
  const played = matches.length
  let wins = 0
  let draws = 0
  let losses = 0
  let gf = 0
  let ga = 0
  for (const m of matches) {
    const r = resultForFocus(m, props.focusTeamId)
    if (r === 'W') wins += 1
    else if (r === 'D') draws += 1
    else if (r === 'L') losses += 1
    const g = goalsForFocus(m, props.focusTeamId)
    if (g) {
      gf += g.gf
      ga += g.ga
    }
  }
  const winRate = played ? Math.round((wins / played) * 100) : 0
  const avgGf = played ? gf / played : 0
  const avgGd = played ? (gf - ga) / played : 0
  return {
    played,
    wins,
    draws,
    losses,
    gf,
    ga,
    winRate,
    avgGf: formatAvg(avgGf),
    avgGd: formatAvg(avgGd),
  }
})
</script>

<template>
  <n-flex v-if="stats.played > 0" align="center" :size="16">
    <n-text strong class="total">
      共<br />{{ stats.played }}场
    </n-text>
    <n-space vertical :size="2" style="flex: 1; min-width: 0">
      <n-text>
        胜率: <span class="tone-win">{{ stats.winRate }}%</span>
      </n-text>
      <n-text>
        <span class="tone-win">{{ stats.wins }}胜</span><span class="tone-draw">{{ stats.draws }}平</span><span class="tone-loss">{{ stats.losses }}负</span><n-text depth="3">，进{{ stats.gf }}失{{ stats.ga }}，场均进球{{ stats.avgGf }}，场均净胜{{ stats.avgGd }}</n-text>
      </n-text>
    </n-space>
  </n-flex>
</template>

<style scoped>
.total {
  flex-shrink: 0;
  text-align: center;
  line-height: 1.15;
  font-size: 15px;
  min-width: 3.2em;
}

.tone-win {
  color: #c23b3b;
  font-weight: 700;
}

.tone-draw {
  color: var(--fa-text-muted);
  font-weight: 700;
}

.tone-loss {
  color: #3b6fc2;
  font-weight: 700;
}
</style>
