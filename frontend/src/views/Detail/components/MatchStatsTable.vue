<script setup lang="ts">
import { computed, h } from 'vue'
import { NEllipsis, type DataTableColumns } from 'naive-ui'

import type { FormMatch } from '@/api/types'
import {
  formatDateYyMmDd,
  homeResultCode,
  htftZh,
  parseScoreGoals,
  resultToZh,
} from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'

const props = withDefaults(
  defineProps<{
    matches: FormMatch[]
    /** Result / name highlight relative to this team. */
    focusTeamId?: number
    emptyDescription?: string
  }>(),
  { emptyDescription: '暂无赛果' },
)

function competitionLabel(m: FormMatch): string {
  return leagueLabel(m.league_name)
}

function focusResultCode(m: FormMatch): string {
  const focusTeamId = props.focusTeamId
  const goals = parseScoreGoals(m.score)
  if (focusTeamId != null && m.home_id != null && m.away_id != null && goals) {
    const [hs, as] = goals
    const hid = Number(m.home_id)
    const aid = Number(m.away_id)
    if (hid === focusTeamId) return homeResultCode(hs, as)
    if (aid === focusTeamId) return homeResultCode(as, hs)
  }
  if (m.result === 'W' || m.result === 'D' || m.result === 'L') return m.result
  if (m.outcome_for_current_home === 'home') return 'W'
  if (m.outcome_for_current_home === 'away') return 'L'
  if (m.outcome_for_current_home === 'draw') return 'D'
  return ''
}

function focusTone(code: string): string {
  if (code === 'W') return 'tone-win'
  if (code === 'D') return 'tone-draw'
  if (code === 'L') return 'tone-loss'
  return ''
}

function zhTone(zh: string): string {
  if (zh === '胜') return 'tone-win'
  if (zh === '平') return 'tone-draw'
  if (zh === '负') return 'tone-loss'
  return ''
}

function teamTone(m: FormMatch, side: 'home' | 'away'): string {
  const focusTeamId = props.focusTeamId
  if (focusTeamId == null) return ''
  const id = side === 'home' ? m.home_id : m.away_id
  if (id == null || Number(id) !== focusTeamId) return ''
  return focusTone(focusResultCode(m))
}

function renderScoreFt(row: FormMatch) {
  const goals = parseScoreGoals(row.score)
  if (!goals) {
    return h('span', { class: 'score-ft' }, row.score || '—')
  }
  const [homeGoals, awayGoals] = goals
  return h('span', { class: 'score-ft' }, [
    h('span', { class: teamTone(row, 'home') || undefined }, String(homeGoals)),
    h('span', { class: 'score-sep' }, '-'),
    h('span', { class: teamTone(row, 'away') || undefined }, String(awayGoals)),
  ])
}

function renderResultCell(row: FormMatch) {
  if ((row.status || '').toLowerCase() === 'pending') {
    return h('span', { class: ['result-text', 'pending'] }, '未开赛')
  }
  const code = focusResultCode(row)
  const ftZh = resultToZh(code)
  const htft = htftZh(row.score, row.score_ht)
  if (!htft) {
    return h('span', { class: ['result-text', focusTone(code)] }, ftZh)
  }
  // 全场(关注队视角) / 半全场(该场主队视角), e.g. 胜/平胜
  return h('span', { class: 'result-text' }, [
    h('span', { class: focusTone(code) }, ftZh),
    h('span', { class: 'result-sep' }, '/'),
    ...[...htft].map((ch) => h('span', { class: zhTone(ch) }, ch)),
  ])
}

const columns = computed<DataTableColumns<FormMatch>>(() => [
  {
    title: '赛事/日期',
    key: 'meta',
    align: 'center',
    width: 108,
    render(row) {
      return h('div', { class: 'meta-cell' }, [
        h(
          NEllipsis,
          { class: 'meta-league' },
          { default: () => competitionLabel(row) || '—' },
        ),
        h('div', { class: 'meta-date' }, formatDateYyMmDd(row.date || '')),
      ])
    },
  },
  {
    title: '主队 比分 客队',
    key: 'matchup',
    align: 'center',
    render(row) {
      return h('div', { class: 'matchup' }, [
        h(
          NEllipsis,
          { class: ['team-name', 'home', teamTone(row, 'home')] },
          { default: () => row.home || '—' },
        ),
        h('span', { class: 'score-block' }, [
          renderScoreFt(row),
          row.score_ht
            ? h('span', { class: 'score-ht' }, `(${row.score_ht})`)
            : null,
        ]),
        h(
          NEllipsis,
          { class: ['team-name', 'away', teamTone(row, 'away')] },
          { default: () => row.away || '—' },
        ),
      ])
    },
  },
  {
    title: '赛果',
    key: 'result',
    align: 'center',
    width: 88,
    render(row) {
      return renderResultCell(row)
    },
  },
])

function rowKey(row: FormMatch): string | number {
  return row.fixture_id ?? `${row.date ?? ''}-${row.home}-${row.away}`
}
</script>

<template>
  <n-empty v-if="!matches.length" :description="emptyDescription" size="small" />
  <n-data-table
    v-else
    size="small"
    :bordered="true"
    :single-line="false"
    :pagination="false"
    :columns="columns"
    :data="matches"
    :row-key="rowKey"
  />
</template>

<style scoped>
/* Cell content only — table chrome comes from n-data-table. */
:deep(.meta-league) {
  font-size: 12px;
  color: var(--fa-text-secondary);
  line-height: 1.3;
}

:deep(.meta-date) {
  margin-top: 2px;
  font-size: 12px;
  color: var(--fa-text-faint);
  line-height: 1.3;
}

:deep(.matchup) {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  column-gap: 10px;
  width: 100%;
}

:deep(.team-name) {
  min-width: 0;
  font-weight: 500;
}

:deep(.team-name.home) {
  text-align: right;
}

:deep(.team-name.away) {
  text-align: left;
}

:deep(.score-block) {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  min-width: 2.8em;
  line-height: 1.15;
}

:deep(.score-ft) {
  font-weight: 700;
  font-size: 14px;
  color: var(--fa-highlight-text);
  font-variant-numeric: tabular-nums;
}

:deep(.score-ht) {
  margin-top: 2px;
  font-size: 11px;
  color: var(--fa-text-faint);
}

:deep(.result-text) {
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

:deep(.result-text.pending) {
  color: var(--fa-text-secondary);
  font-weight: 500;
}

:deep(.result-sep) {
  margin: 0 1px;
  color: var(--fa-text-faint);
  font-weight: 500;
}

:deep(.tone-win) {
  color: var(--fa-wdl-win);
  font-weight: 700;
}

:deep(.tone-loss) {
  color: var(--fa-wdl-loss);
  font-weight: 700;
}

:deep(.tone-draw) {
  color: var(--fa-wdl-draw);
  font-weight: 600;
}
</style>
