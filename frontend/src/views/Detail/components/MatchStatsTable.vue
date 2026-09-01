<script setup lang="ts">
import { computed, h } from 'vue'
import { NEllipsis, type DataTableColumns } from 'naive-ui'

import type { FormMatch, HistoryAhLine } from '@/api/types'
import { formatDateYyMmDd, formatOdd, homeResultCode, leagueTagColor, parseScoreGoals, resultToZh } from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'

const props = withDefaults(
  defineProps<{
    matches: FormMatch[]
    /** Result / name highlight relative to this team. */
    focusTeamId?: number
    emptyDescription?: string
    /** H2H: also show locally stored opening / current AH main lines. */
    showOdds?: boolean
  }>(),
  { emptyDescription: '暂无赛果', showOdds: false },
)

function competitionLabel(m: FormMatch): string {
  return leagueLabel(m.league_name)
}

function leagueCellStyle(row: FormMatch) {
  if (row.league_id == null) return undefined
  const color = leagueTagColor(Number(row.league_id))
  return { backgroundColor: `${color}18`, color }
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
  if ((row.status ?? '').toLowerCase() === 'pending') {
    return h('span', { class: ['result-text', 'pending'] }, '未开赛')
  }
  const code = focusResultCode(row)
  return h('span', { class: ['result-text', focusTone(code)] }, resultToZh(code))
}

function renderAh(line?: HistoryAhLine | null) {
  if (!line?.line) {
    return h('span', { class: 'ah-empty' }, '—')
  }
  return h('span', { class: 'ah-cell' }, [
    h('span', {}, formatOdd(line.home)),
    h('span', { class: 'ah-line' }, line.line),
    h('span', {}, formatOdd(line.away)),
  ])
}

const columns = computed<DataTableColumns<FormMatch>>(() => {
  const cols: DataTableColumns<FormMatch> = [
    {
      title: '赛事',
      key: 'league',
      align: 'center',
      width: 88,
      className: 'league-col',
      cellProps(row) {
        return { style: leagueCellStyle(row) }
      },
      render(row) {
        return h(NEllipsis, {}, { default: () => competitionLabel(row) || '—' })
      },
    },
    {
      title: '日期',
      key: 'date',
      align: 'center',
      width: 78,
      render(row) {
        return h('span', { class: 'date-cell' }, formatDateYyMmDd(row.date || ''))
      },
    },
    {
      title: '半场',
      key: 'score_ht',
      align: 'center',
      width: 52,
      render(row) {
        return h('span', { class: 'ht-cell' }, row.score_ht || '—')
      },
    },
    {
      title: '主队 比分 客队',
      key: 'matchup',
      align: 'center',
      minWidth: 168,
      render(row) {
        return h('div', { class: 'matchup' }, [
          h(
            NEllipsis,
            { class: ['team-name', 'home', teamTone(row, 'home')] },
            { default: () => row.home || '—' },
          ),
          renderScoreFt(row),
          h(
            NEllipsis,
            { class: ['team-name', 'away', teamTone(row, 'away')] },
            { default: () => row.away || '—' },
          ),
        ])
      },
    },
  ]
  if (props.showOdds) {
    cols.push(
      {
        title: '初盘',
        key: 'ah_opening',
        align: 'center',
        width: 118,
        render(row) {
          return renderAh(row.ah_opening)
        },
      },
      {
        title: '即时盘',
        key: 'ah_current',
        align: 'center',
        width: 118,
        render(row) {
          return renderAh(row.ah_current)
        },
      },
    )
  }
  cols.push({
    title: '赛果',
    key: 'result',
    align: 'center',
    width: 52,
    render(row) {
      return renderResultCell(row)
    },
  })
  return cols
})

function rowKey(row: FormMatch): string | number {
  return row.fixture_id ?? `${row.date ?? ''}-${row.home}-${row.away}`
}

const scrollX = computed(() => (props.showOdds ? 780 : 520))
</script>

<template>
  <n-empty v-if="!matches.length" :description="emptyDescription" size="small" />
  <n-data-table
    v-else
    size="small"
    :bordered="true"
    :single-line="false"
    :pagination="false"
    :scroll-x="scrollX"
    :columns="columns"
    :data="matches"
    :row-key="rowKey"
    class="stats-table"
  />
</template>

<style scoped>
.stats-table :deep(.n-data-table-th) {
  padding: 6px 8px;
  font-size: 12px;
}

.stats-table :deep(.n-data-table-td) {
  padding: 4px 8px;
}

.stats-table :deep(.league-col) {
  background: var(--fa-bg-soft);
}

:deep(.date-cell),
:deep(.ht-cell) {
  font-size: 12px;
  color: var(--fa-text-secondary);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

:deep(.matchup) {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  column-gap: 8px;
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

:deep(.score-ft) {
  font-weight: 700;
  font-size: 13px;
  color: var(--fa-highlight-text);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

:deep(.score-sep) {
  margin: 0 1px;
}

:deep(.ah-cell) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  color: var(--fa-text);
}

:deep(.ah-line) {
  font-weight: 700;
  color: var(--fa-highlight-text);
}

:deep(.ah-empty) {
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
