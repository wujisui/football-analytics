<script setup lang="ts">
import { ChevronForwardOutline, SearchOutline } from '@vicons/ionicons5'
import { computed, ref } from 'vue'

import { fuzzyIncludes } from '@/utils/fuzzySearch'
import type { LeagueSummaryResponse } from '@/api/types'
import { leagueTagColor } from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'

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

const searchQuery = ref('')

function abbrOf(name: string): string {
  const trimmed = name.trim()
  if (!trimmed) return '?'
  const m = trimmed.match(/[\u4e00-\u9fffA-Za-z0-9]/)
  return (m?.[0] ?? trimmed[0]).toUpperCase()
}

const sortedLeagues = computed(() =>
  [...props.leagues].sort((a, b) =>
    leagueLabel(a.league_name).localeCompare(leagueLabel(b.league_name), 'zh'),
  ),
)

const filteredLeagues = computed(() => {
  const q = searchQuery.value.trim()
  if (!q) return sortedLeagues.value
  return sortedLeagues.value.filter((league) => {
    const name = leagueLabel(league.league_name)
    const country = league.country || ''
    return fuzzyIncludes(name, q) || fuzzyIncludes(country, q)
  })
})

const showAllRow = computed(() => {
  const q = searchQuery.value.trim()
  if (!q) return true
  return fuzzyIncludes('全部', q)
})

function selectAll() {
  emit('select', null)
}

function selectLeague(leagueId: number) {
  emit('select', leagueId)
}

function countOf(leagueId: number): number {
  return props.pendingCountByLeague.get(leagueId) || 0
}
</script>

<template>
  <div class="league-menu" :class="{ collapsed }">
    <div class="lm-toolbar">
      <n-input
        v-if="!collapsed"
        v-model:value="searchQuery"
        class="lm-search"
        size="small"
        placeholder="搜索联赛或国家"
        clearable
      >
        <template #prefix>
          <n-icon :component="SearchOutline" :size="14" />
        </template>
      </n-input>
      <div class="lm-toolbar-actions">
        <slot name="filter" />
      </div>
    </div>

    <n-spin :show="!!loading" class="lm-body">
      <n-empty
        v-if="!loading && leagues.length === 0"
        description="暂无联赛"
        size="small"
        class="lm-empty"
      />
      <n-scrollbar v-else class="lm-scroll">
        <div class="lm-list" role="list">
          <button
            v-if="showAllRow"
            type="button"
            role="listitem"
            class="lm-row"
            :class="{ active: selectedLeagueId == null }"
            :title="collapsed ? `全部 (${totalPending})` : undefined"
            @click="selectAll"
          >
            <span class="lm-chip lm-chip-all" aria-hidden="true">全</span>
            <span v-if="!collapsed" class="lm-name">全部</span>
            <span v-if="!collapsed" class="lm-meta">
              <span v-if="totalPending > 0" class="lm-count">{{ totalPending }}</span>
              <n-icon :component="ChevronForwardOutline" :size="14" class="lm-chevron" />
            </span>
          </button>

          <button
            v-for="league in filteredLeagues"
            :key="league.league_id"
            type="button"
            role="listitem"
            class="lm-row"
            :class="{ active: selectedLeagueId === league.league_id }"
            :title="collapsed ? leagueLabel(league.league_name) : undefined"
            @click="selectLeague(league.league_id)"
          >
            <span
              class="lm-chip"
              :style="{
                background: `${leagueTagColor(league.league_id)}18`,
                color: leagueTagColor(league.league_id),
                borderColor: `${leagueTagColor(league.league_id)}40`,
              }"
              aria-hidden="true"
            >
              {{ abbrOf(leagueLabel(league.league_name)) }}
            </span>
            <span v-if="!collapsed" class="lm-name">{{ leagueLabel(league.league_name) }}</span>
            <span v-if="!collapsed" class="lm-meta">
              <span v-if="countOf(league.league_id) > 0" class="lm-count">
                {{ countOf(league.league_id) }}
              </span>
              <n-icon :component="ChevronForwardOutline" :size="14" class="lm-chevron" />
            </span>
          </button>

          <div
            v-if="!loading && !showAllRow && filteredLeagues.length === 0"
            class="lm-no-match"
          >
            无匹配联赛
          </div>
        </div>
      </n-scrollbar>
    </n-spin>
  </div>
</template>

<style scoped>
.league-menu {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--fa-bg-elevated);
}

.lm-toolbar {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: stretch;
  gap: 6px;
  padding: 10px 8px 8px;
  flex-shrink: 0;
  background: var(--fa-bg-elevated);
}

.league-menu.collapsed .lm-toolbar {
  justify-content: center;
  padding: 10px 4px 8px;
}

.lm-search {
  flex: 1;
  min-width: 0;
}

.lm-toolbar-actions {
  display: inline-flex;
  align-items: stretch;
  flex-shrink: 0;
}

.lm-toolbar-actions :deep(.league-filter-btn:not(.is-icon-only)) {
  height: 100%;
}

.lm-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.lm-body :deep(.n-spin-container),
.lm-body :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.lm-scroll {
  flex: 1;
  min-height: 0;
}

.lm-scroll :deep(.n-scrollbar) {
  height: 100%;
  max-height: 100%;
}

.lm-list {
  padding: 0 8px 12px;
}

.lm-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  margin: 0;
  padding: 8px 10px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--fa-text);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.league-menu.collapsed .lm-row {
  justify-content: center;
  padding: 8px 4px;
}

.lm-row:hover:not(.active) {
  background: color-mix(in srgb, var(--fa-text) 7%, transparent);
}

.lm-row.active {
  color: var(--n-primary-color, #18a058);
  background: color-mix(in srgb, var(--n-primary-color, #18a058) 14%, transparent);
}

.lm-row.active .lm-name {
  font-weight: 600;
  color: inherit;
}

.lm-row.active .lm-meta,
.lm-row.active .lm-count,
.lm-row.active .lm-chevron {
  color: inherit;
  opacity: 1;
}

.lm-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  min-width: 28px;
  border-radius: 6px;
  border: 1px solid var(--fa-border);
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  flex-shrink: 0;
}

.lm-chip-all {
  background: var(--fa-bg-soft);
  color: var(--fa-text-secondary);
}

.lm-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lm-meta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  color: var(--fa-text-muted);
}

.lm-count {
  min-width: 1.2em;
  text-align: right;
  font-size: 12px;
  font-weight: 600;
}

.lm-chevron {
  opacity: 0.55;
}

.lm-row.active .lm-chip-all {
  color: inherit;
  border-color: color-mix(in srgb, var(--n-primary-color, #18a058) 35%, transparent);
  background: color-mix(in srgb, var(--n-primary-color, #18a058) 10%, transparent);
}

.lm-empty {
  padding: 24px 12px;
}

.lm-no-match {
  padding: 16px 14px;
  font-size: 12px;
  color: var(--fa-text-muted);
  text-align: center;
}
</style>
