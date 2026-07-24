<script setup lang="ts">
import { computed, h } from 'vue'
import type { DataTableColumns } from 'naive-ui'
import { NButton, NDataTable, NPopover } from 'naive-ui'
import { useRouter } from 'vue-router'

import type { DetailFrom } from '@/utils/detailNav'
import { fixtureDetailRoute } from '@/utils/detailNav'
import { formatOdd } from '@/utils/format'
import { ahLinesOf, hasOddsMarkets, type OddsLike } from '@/utils/oddsDisplay'

type OddsRow = {
  key: string
  play: string
  home: string
  mid: string
  away: string
  midKind: 'text' | 'line' | 'popover'
}

const props = withDefaults(
  defineProps<{
    odds: OddsLike
    homeName: string
    awayName: string
    linkMiddleToDetail?: boolean
    fixtureId?: number
    from?: DetailFrom
    detailTab?: 'prediction' | 'briefing'
    date?: string | null
    emptyText?: string
  }>(),
  {
    linkMiddleToDetail: false,
    from: 'home',
    detailTab: 'prediction',
    date: null,
    emptyText: '暂无盘口（打开详情拉取后显示）',
  },
)

const router = useRouter()

const mw = computed(() => props.odds?.match_winner ?? null)
const ou = computed(() => props.odds?.goals_ou ?? null)
const ahLines = computed(() => ahLinesOf(props.odds?.asian_handicap))
const ahExtraCount = computed(() => Math.max(0, ahLines.value.length - 1))
const showMarkets = computed(() => hasOddsMarkets(props.odds))

const ahRows = computed(() => (ahLines.value.length ? [ahLines.value[0]] : []))

function middleLinkable(): boolean {
  return !!(props.linkMiddleToDetail && props.fixtureId)
}

function goDetail() {
  if (!props.fixtureId) return
  void router.push(
    fixtureDetailRoute(props.fixtureId, {
      from: props.from,
      tab: props.detailTab,
      date: props.date,
    }),
  )
}

const tableRows = computed((): OddsRow[] => {
  const rows: OddsRow[] = []

  if (mw.value) {
    rows.push({
      key: 'mw',
      play: '胜平负',
      home: formatOdd(mw.value.home),
      mid: formatOdd(mw.value.draw),
      away: formatOdd(mw.value.away),
      midKind: 'text',
    })
  }

  ahRows.value.forEach((line, idx) => {
    const usePopover = idx === 0 && ahExtraCount.value > 0
    rows.push({
      key: `ah-${line.line}-${idx}`,
      play: idx === 0 ? '让球' : '',
      home: formatOdd(line.home),
      mid: line.line || '—',
      away: formatOdd(line.away),
      midKind: usePopover ? 'popover' : 'line',
    })
  })

  if (ou.value) {
    rows.push({
      key: 'ou',
      play: '大小',
      home: formatOdd(ou.value.home),
      mid: ou.value.line || '—',
      away: formatOdd(ou.value.away),
      midKind: 'line',
    })
  }

  return rows
})

function buildColumns(linkMidHeader: boolean): DataTableColumns<OddsRow> {
  return [
    {
      title: '玩法',
      key: 'play',
      align: 'center',
      width: 72,
      render: (row) => {
        if (!row.play) return null
        const showExtra = row.midKind === 'popover' && ahExtraCount.value > 0
        return h('span', { class: 'play-cell' }, [
          row.play,
          showExtra ? h('span', { class: 'ah-more' }, ` +${ahExtraCount.value}`) : null,
        ])
      },
    },
    {
      title: '主队',
      key: 'home',
      align: 'center',
      render: (row) => h('span', { class: 'value-cell' }, row.home),
    },
    {
      title: () =>
        linkMidHeader
          ? h(
              NButton,
              {
                text: true,
                type: 'primary',
                size: 'small',
                onClick: goDetail,
              },
              { default: () => '指数' },
            )
          : '指数',
      key: 'mid',
      align: 'center',
      width: 72,
      render: (row) => renderMidCell(row),
    },
    {
      title: '客队',
      key: 'away',
      align: 'center',
      render: (row) => h('span', { class: 'value-cell' }, row.away),
    },
  ]
}

const columns = computed(() => buildColumns(middleLinkable()))

function renderAhPopover() {
  return h('div', { class: 'ah-popover-panel' }, [
    h('div', { class: 'ah-popover-row ah-popover-head' }, [
      h('span', { class: 'ah-popover-label' }, '让球'),
      h('span', { class: 'ah-popover-col' }, props.homeName),
      h('span', { class: 'ah-popover-col mid' }, '盘口'),
      h('span', { class: 'ah-popover-col' }, props.awayName),
    ]),
    ...ahLines.value.map((line, idx) =>
      h('div', { class: 'ah-popover-row', key: `ah-pop-${line.line}-${idx}` }, [
        h('span', { class: 'ah-popover-label' }),
        h('span', { class: 'ah-popover-col' }, formatOdd(line.home)),
        h('span', { class: 'ah-popover-col mid line' }, line.line || '—'),
        h('span', { class: 'ah-popover-col' }, formatOdd(line.away)),
      ]),
    ),
  ])
}

function renderMidCell(row: OddsRow) {
  if (row.midKind === 'popover') {
    return h(
      NPopover,
      {
        trigger: 'hover',
        placement: 'bottom',
        showArrow: false,
        delay: 120,
        raw: true,
      },
      {
        trigger: () =>
          h(
            'button',
            {
              type: 'button',
              class: 'ah-line-trigger',
              'aria-label': `主盘 ${row.mid}，另有 ${ahExtraCount.value} 条让球盘`,
            },
            row.mid,
          ),
        default: () => renderAhPopover(),
      },
    )
  }
  return h(
    'span',
    { class: row.midKind === 'line' ? 'mid-line' : 'mid-text' },
    row.mid,
  )
}
</script>

<template>
  <n-empty v-if="!showMarkets" :description="emptyText" size="small" />
  <n-data-table
    v-else
    class="pre-match-odds-table"
    size="small"
    :bordered="true"
    :single-line="false"
    :pagination="false"
    :columns="columns"
    :data="tableRows"
    :row-key="(row: OddsRow) => row.key"
  />
</template>

<style scoped>
.pre-match-odds-table {
  align-self: start;
  width: 100%;
}

.pre-match-odds-table :deep(.n-data-table),
.pre-match-odds-table :deep(.n-data-table-wrapper) {
  height: auto;
}

/* Cell content — table chrome matches MatchStatsTable (n-data-table). */
:deep(.play-cell) {
  font-size: 12px;
  color: var(--fa-text-secondary);
  font-weight: 500;
}

:deep(.value-cell) {
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--fa-text);
}

:deep(.mid-text) {
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--fa-text);
}

:deep(.mid-line) {
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--fa-text-strong);
}

:deep(.ah-line-trigger) {
  appearance: none;
  margin: 0;
  padding: 0;
  border: none;
  background: none;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--fa-text-strong);
  cursor: default;
  text-decoration: underline;
  text-decoration-style: dotted;
  text-underline-offset: 3px;
}

:deep(.ah-line-trigger:hover),
:deep(.ah-line-trigger:focus-visible) {
  background: var(--fa-bg-soft);
  border-radius: 2px;
  outline: none;
}

:deep(.ah-more) {
  margin-left: 2px;
  font-size: 10px;
  font-weight: 600;
  color: var(--fa-accent, #2080f0);
}
</style>

<style>
.ah-popover-panel {
  min-width: 280px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--fa-border);
  background: var(--fa-bg-elevated);
  box-shadow: 0 8px 24px var(--fa-hover-shadow);
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--fa-text-secondary);
}

.ah-popover-row {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) 52px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}

.ah-popover-head {
  margin-bottom: 2px;
  color: var(--fa-text-faint);
  font-size: 11px;
}

.ah-popover-label {
  text-align: left;
  color: var(--fa-text-faint);
}

.ah-popover-col {
  text-align: center;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--fa-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ah-popover-col.mid {
  color: var(--fa-text-secondary);
}

.ah-popover-col.line {
  font-weight: 700;
  color: var(--fa-accent, #2080f0);
}

.ah-popover-head .ah-popover-col {
  font-weight: 500;
  color: var(--fa-text-faint);
}
</style>
