<script setup lang="ts">
import type { MenuOption } from 'naive-ui'
import { NBadge } from 'naive-ui'
import { computed, h, type VNodeChild } from 'vue'

import type { LeagueSummaryResponse } from '@/api/types'
import { leagueTagColor } from '@/utils/format'
import { leagueNameZh } from '@/utils/leagueNames'

const props = defineProps<{
  leagues: LeagueSummaryResponse[]
  selectedLeagueId: number | null
  pendingCountByLeague: Map<number, number>
  totalPending: number
  loading?: boolean
  collapsed?: boolean
}>()

const emit = defineEmits<{
  select: [leagueId: number | null]
}>()

const activeKey = computed(() =>
  props.selectedLeagueId == null ? 'all' : String(props.selectedLeagueId),
)

function abbrOf(name: string): string {
  const trimmed = name.trim()
  if (!trimmed) return '?'
  const m = trimmed.match(/[\u4e00-\u9fffA-Za-z0-9]/)
  return (m?.[0] ?? trimmed[0]).toUpperCase()
}

function allIcon(): VNodeChild {
  return h(
    'span',
    {
      class: 'menu-chip all',
      'aria-hidden': 'true',
    },
    [
      h(
        'svg',
        {
          viewBox: '0 0 24 24',
          width: '15',
          height: '15',
          fill: 'none',
          stroke: 'currentColor',
          'stroke-width': '2',
          'stroke-linecap': 'round',
        },
        [
          h('rect', { x: '3', y: '3', width: '7', height: '7', rx: '1.5' }),
          h('rect', { x: '14', y: '3', width: '7', height: '7', rx: '1.5' }),
          h('rect', { x: '3', y: '14', width: '7', height: '7', rx: '1.5' }),
          h('rect', { x: '14', y: '14', width: '7', height: '7', rx: '1.5' }),
        ],
      ),
    ],
  )
}

function leagueIcon(name: string, color: string): VNodeChild {
  return h(
    'span',
    {
      class: 'menu-chip',
      style: {
        background: `${color}18`,
        color,
        borderColor: `${color}40`,
      },
      'aria-hidden': 'true',
    },
    abbrOf(name),
  )
}

/** Collapsed only: one soft badge on the chip when count > 0. */
function collapsedIcon(count: number, child: VNodeChild): VNodeChild {
  if (count <= 0) return child
  return h(
    NBadge,
    {
      value: count,
      max: 99,
      showZero: false,
      type: 'info',
      offset: [-4, 2],
    },
    { default: () => child },
  )
}

function expandedLabel(name: string, count: number): () => VNodeChild {
  return () =>
    h('div', { class: 'menu-label-row' }, [
      h('span', { class: 'menu-name' }, name),
      count > 0
        ? h('span', { class: 'menu-count' }, String(count))
        : null,
    ])
}

const menuOptions = computed<MenuOption[]>(() => {
  const collapsed = !!props.collapsed

  const all: MenuOption = {
    key: 'all',
    label: collapsed ? '全部' : expandedLabel('全部', props.totalPending),
    icon: () =>
      collapsed
        ? collapsedIcon(props.totalPending, allIcon())
        : allIcon(),
  }

  const items = props.leagues.map((league) => {
    const count = props.pendingCountByLeague.get(league.league_id) || 0
    const color = leagueTagColor(league.league_id)
    const name = leagueNameZh(league.league_name)
    const chip = leagueIcon(name, color)
    return {
      key: String(league.league_id),
      label: collapsed
        ? name
        : expandedLabel(name, count),
      icon: () => (collapsed ? collapsedIcon(count, chip) : chip),
    } satisfies MenuOption
  })

  return [all, ...items]
})

function onUpdateValue(key: string) {
  if (key === 'all') {
    emit('select', null)
    return
  }
  emit('select', Number(key))
}
</script>

<template>
  <div class="league-menu" :class="{ collapsed }">
    <div class="menu-title">
      <span v-if="!collapsed" class="menu-title-text">联赛筛选</span>
      <div class="menu-title-actions">
        <slot name="filter" />
      </div>
    </div>

    <n-spin :show="!!loading">
      <n-empty
        v-if="!loading && leagues.length === 0"
        description="暂无联赛"
        size="small"
        class="menu-empty"
      />
      <n-menu
        v-else
        :value="activeKey"
        :options="menuOptions"
        :collapsed="!!collapsed"
        :collapsed-width="64"
        :collapsed-icon-size="28"
        :icon-size="28"
        :root-indent="collapsed ? 0 : 12"
        :indent="12"
        @update:value="onUpdateValue"
      />
    </n-spin>
  </div>
</template>

<style scoped>
.league-menu {
  padding: 12px 0 16px;
  height: 100%;
  box-sizing: border-box;
}

.league-menu.collapsed {
  padding: 10px 0 16px;
}

.menu-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--fa-text-muted);
  padding: 0 12px 10px 20px;
  letter-spacing: 0.04em;
  min-height: 28px;
}

.league-menu.collapsed .menu-title {
  padding: 0 0 10px;
  justify-content: center;
}

.menu-title-text {
  flex: 1;
  min-width: 0;
}

.menu-title-actions {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
}

.menu-empty {
  padding: 24px 12px;
}

.menu-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-width: 0;
  padding-right: 4px;
}

.menu-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.menu-count {
  flex-shrink: 0;
  min-width: 1.25em;
  padding: 0 6px;
  height: 20px;
  line-height: 20px;
  border-radius: 999px;
  text-align: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--fa-text-secondary);
  background: var(--fa-bg-soft);
}

:deep(.menu-chip) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  min-width: 28px;
  min-height: 28px;
  flex-shrink: 0;
  border-radius: 8px;
  border: 1px solid var(--fa-border);
  background: var(--fa-bg-soft);
  color: var(--fa-text);
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
  box-sizing: border-box;
}

:deep(.menu-chip.all) {
  color: var(--fa-text-secondary);
}

:deep(.menu-chip.all svg) {
  width: 15px;
  height: 15px;
  display: block;
  flex-shrink: 0;
}

:deep(.n-menu .n-menu-item-content) {
  padding-right: 12px !important;
}

:deep(.n-menu-item-content__icon) {
  margin-right: 10px !important;
  width: 28px !important;
  height: 28px !important;
  min-width: 28px !important;
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  font-size: 28px !important;
}

.league-menu.collapsed :deep(.n-menu .n-menu-item-content) {
  padding-right: 0 !important;
  justify-content: center;
}

.league-menu.collapsed :deep(.n-menu-item-content__icon) {
  margin-right: 0 !important;
  width: 28px !important;
  height: 28px !important;
}

:deep(.n-badge .n-badge-sup) {
  font-size: 10px;
  padding: 0 4px;
  height: 16px;
  line-height: 16px;
  box-shadow: none;
}
</style>
