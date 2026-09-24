<script setup lang="ts">
import { computed, h } from 'vue'
import type { DataTableColumns } from 'naive-ui'

import type { FormMatch, HistoryMarketLine } from '@/api/types'
import { formatDateYyMmDd } from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'

const props = withDefaults(
  defineProps<{
    matches: FormMatch[]
    /** AH line and settlement are shown from this team's point of view. */
    focusTeamId?: number
    emptyDescription?: string
  }>(),
  { emptyDescription: '暂无赛果' },
)

function competitionLabel(m: FormMatch): string {
  return leagueLabel(m.league_name)
}

function isPending(row: FormMatch): boolean {
  return (row.status ?? '').toLowerCase() === 'pending'
}

function lineNumber(raw: string): number | null {
  const text = raw.trim().replace(',', '.')
  if (!text) return null
  if (text.includes('/')) {
    const negative = text.startsWith('-')
    const values = text
      .replace(/^[+-]/, '')
      .split('/')
      .map(Number)
    if (values.length !== 2 || values.some((value) => !Number.isFinite(value))) {
      return null
    }
    const average = (values[0] + values[1]) / 2
    return negative ? -average : average
  }
  const value = Number(text)
  return Number.isFinite(value) ? value : null
}

/** 0.75 → 0.5/1, preserving the selected team's +/- AH direction. */
function asianLineLabel(line?: HistoryMarketLine | null, invert = false): string {
  if (!line?.line) return '—'
  const parsed = lineNumber(line.line)
  if (parsed == null) return line.line
  const value = invert ? -parsed : parsed
  if (Math.abs(value) < 1e-9) return '0'
  const sign = value > 0 ? '+' : '-'
  const abs = Math.abs(value)
  const quarters = Math.round(abs * 4)
  if (Math.abs(abs * 4 - quarters) < 1e-7 && quarters % 2 === 1) {
    const lower = (quarters - 1) / 4
    const upper = (quarters + 1) / 4
    return `${sign}${compactNumber(lower)}/${compactNumber(upper)}`
  }
  return `${sign}${compactNumber(abs)}`
}

function totalLineLabel(line?: HistoryMarketLine | null): string {
  if (!line?.line) return '—'
  const parsed = lineNumber(line.line)
  if (parsed == null) return line.line
  const quarters = Math.round(parsed * 4)
  if (Math.abs(parsed * 4 - quarters) < 1e-7 && quarters % 2 === 1) {
    return `${compactNumber((quarters - 1) / 4)}/${compactNumber((quarters + 1) / 4)}`
  }
  return compactNumber(parsed)
}

function compactNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)))
}

function focusIsAway(row: FormMatch): boolean {
  return (
    props.focusTeamId != null &&
    row.away_id != null &&
    Number(row.away_id) === props.focusTeamId
  )
}

function ahResultLabel(result: FormMatch['ah_result']): string {
  if (!result) return '—'
  return {
    win: '赢',
    half_win: '赢半',
    push: '走',
    half_loss: '输半',
    loss: '输',
  }[result]
}

function ouResultLabel(result: FormMatch['ou_result']): string {
  if (!result) return '—'
  return {
    over: '大',
    over_half: '大半',
    push: '走',
    under_half: '小半',
    under: '小',
  }[result]
}

function settlementTone(result?: string | null): string {
  if (result === 'win' || result === 'half_win' || result === 'over' || result === 'over_half') {
    return 'tone-win'
  }
  if (result === 'loss' || result === 'half_loss' || result === 'under' || result === 'under_half') {
    return 'tone-loss'
  }
  return result === 'push' ? 'tone-draw' : ''
}

function renderTwoLines(primary: string, secondary: string, tone = '') {
  return h('div', { class: 'two-line-cell' }, [
    h('span', { class: 'primary-line' }, primary),
    h('span', { class: ['secondary-line', tone] }, secondary),
  ])
}

const columns = computed<DataTableColumns<FormMatch>>(() => {
  return [
    {
      title: '日期/赛事',
      key: 'date_league',
      align: 'center',
      width: 70,
      render(row) {
        return renderTwoLines(
          formatDateYyMmDd(row.date || '') || '—',
          competitionLabel(row) || '—',
        )
      },
    },
    {
      title: '对阵',
      key: 'matchup',
      align: 'center',
      minWidth: 150,
      render(row) {
        // Home / score / away are fixed grid tracks so the halftime score in
        // the second row always sits under the full-time score, whatever the
        // team names measure.
        return h('div', { class: 'matchup-cell' }, [
          h('span', { class: ['team-name', 'home'] }, row.home || '—'),
          h('span', { class: 'score-ft' }, row.score || '—'),
          h('span', { class: ['team-name', 'away'] }, row.away || '—'),
          h(
            'span',
            { class: ['secondary-line', 'score-ht'] },
            row.score_ht ? `(${row.score_ht})` : '—',
          ),
        ])
      },
    },
    {
      title: '让球',
      key: 'ah',
      align: 'center',
      width: 54,
      render(row) {
        const invert = focusIsAway(row)
        const current = asianLineLabel(row.ah_current ?? row.ah_opening, invert)
        const secondary = isPending(row)
          ? asianLineLabel(row.ah_opening, invert)
          : ahResultLabel(row.ah_result)
        return renderTwoLines(
          current,
          secondary,
          isPending(row) ? '' : settlementTone(row.ah_result),
        )
      },
    },
    {
      title: '总进球',
      key: 'ou',
      align: 'center',
      width: 54,
      render(row) {
        const current = totalLineLabel(row.ou_current ?? row.ou_opening)
        const secondary = isPending(row)
          ? totalLineLabel(row.ou_opening)
          : ouResultLabel(row.ou_result)
        return renderTwoLines(
          current,
          secondary,
          isPending(row) ? '' : settlementTone(row.ou_result),
        )
      },
    },
  ]
})

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
    class="stats-table"
  />
</template>

<style scoped>
/* No cell padding: the 1.6 line-height below already keeps text off the
   borders, and the saved width goes to the team names. */
.stats-table :deep(.n-data-table-th),
.stats-table :deep(.n-data-table-td) {
  padding: 0;
  font-size: 12px;
  line-height: 1.6;
}

:deep(.two-line-cell) {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

/* 主队 / 比分 / 客队 are three tracks shared by both rows, so the halftime
   score lands directly under the full-time score in every row. */
:deep(.matchup-cell) {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  justify-items: center;
  min-width: 0;
  column-gap: 5px;
}

:deep(.primary-line) {
  color: var(--fa-text);
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

:deep(.secondary-line) {
  font-size: 12px;
  color: var(--fa-text-secondary);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

:deep(.team-name) {
  overflow: hidden;
  max-width: 100%;
  min-width: 0;
  text-overflow: ellipsis;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

:deep(.team-name.home) {
  justify-self: end;
}

:deep(.team-name.away) {
  justify-self: start;
}

:deep(.score-ft) {
  font-weight: 700;
  font-size: 12px;
  color: var(--fa-highlight-text);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* Second row: only the middle track is filled. */
:deep(.score-ht) {
  grid-column: 2;
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

@media (max-width: 480px) {
  :deep(.matchup-cell) {
    column-gap: 3px;
  }
}
</style>
