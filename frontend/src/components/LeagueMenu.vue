<script setup lang="ts">
import type { MenuOption } from 'naive-ui'
import { NBadge } from 'naive-ui'
import { computed, h } from 'vue'

import type { LeagueSummaryResponse } from '@/api/types'
import { leagueTagColor } from '@/utils/format'

const props = defineProps<{
  leagues: LeagueSummaryResponse[]
  selectedLeagueId: number | null
  pendingCountByLeague: Map<number, number>
  totalPending: number
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [leagueId: number | null]
}>()

const activeKey = computed(() =>
  props.selectedLeagueId == null ? 'all' : String(props.selectedLeagueId),
)

function menuLabel(name: string, count: number, color?: string) {
  return () =>
    h(
      'div',
      {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          width: '100%',
        },
      },
      [
        h('span', {
          style: {
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: color || '#666',
            flexShrink: '0',
          },
        }),
        h(
          'span',
          {
            style: {
              flex: '1',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            },
          },
          name,
        ),
        h(
          NBadge,
          {
            value: count,
            max: 99,
            type: 'default',
            showZero: true,
          },
          {},
        ),
      ],
    )
}

const menuOptions = computed<MenuOption[]>(() => {
  const all: MenuOption = {
    label: menuLabel('全部', props.totalPending),
    key: 'all',
  }
  const items = props.leagues.map((league) => ({
    label: menuLabel(
      league.league_name,
      props.pendingCountByLeague.get(league.league_id) || 0,
      leagueTagColor(league.league_id),
    ),
    key: String(league.league_id),
  }))
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
  <div class="league-menu">
    <div class="menu-title">联赛筛选</div>
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
        :root-indent="12"
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
}

.menu-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--fa-text-muted);
  padding: 0 20px 8px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.menu-empty {
  padding: 24px 12px;
}

:deep(.n-menu .n-menu-item-content) {
  padding-right: 12px !important;
}

:deep(.n-badge .n-badge-sup) {
  font-size: 11px;
}
</style>
