<script setup lang="ts">
import { computed, h } from 'vue'
import type { DataTableColumns } from 'naive-ui'

import type { FormMatch } from '@/api/types'
import { formatDateYyMmDd, resultToZh } from '@/utils/format'
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
  if (focusTeamId != null && m.home_id != null && m.away_id != null) {
    const hid = Number(m.home_id)
    const aid = Number(m.away_id)
    const [hs, as] = String(m.score || '')
      .split('-')
      .map((x) => Number(x.trim()))
    if (Number.isFinite(hs) && Number.isFinite(as)) {
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

const columns = computed<DataTableColumns<FormMatch>>(() => [
  {
    title: '赛事/日期',
    key: 'meta',
    align: 'center',
    width: 108,
    render(row) {
      return h('div', { class: 'meta-cell' }, [
        h('div', { class: 'meta-league' }, competitionLabel(row) || '—'),
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
          'span',
          { class: ['team-name', 'home', teamTone(row, 'home')] },
          row.home || '—',
        ),
        h('span', { class: 'score-block' }, [
          h('span', { class: 'score-ft' }, row.score),
          row.score_ht
            ? h('span', { class: 'score-ht' }, `(${row.score_ht})`)
            : null,
        ]),
        h(
          'span',
          { class: ['team-name', 'away', teamTone(row, 'away')] },
          row.away || '—',
        ),
      ])
    },
  },
  {
    title: '赛果',
    key: 'result',
    align: 'center',
    width: 64,
    render(row) {
      const code = focusResultCode(row)
      return h(
        'span',
        { class: ['result-text', focusTone(code)] },
        resultToZh(code),
      )
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
}

:deep(.score-ht) {
  margin-top: 2px;
  font-size: 11px;
  color: var(--fa-text-faint);
}

:deep(.result-text) {
  font-size: 13px;
  font-weight: 700;
}

:deep(.tone-win) {
  color: #c23b3b;
  font-weight: 700;
}

:deep(.tone-loss) {
  color: #3b6fc2;
  font-weight: 700;
}

:deep(.tone-draw) {
  color: var(--fa-text-muted);
  font-weight: 600;
}
</style>
