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
  countByLeague: Map<number, number>
  totalCount: number
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
  return props.countByLeague.get(leagueId) || 0
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
        <n-list
          class="lm-list"
          hoverable
          clickable
          :show-divider="false"
        >
          <n-list-item
            v-if="showAllRow"
            class="lm-item"
            :class="{ active: selectedLeagueId == null }"
            @click="selectAll"
          >
            <template #prefix>
              <n-tooltip :disabled="!collapsed" placement="right">
                <template #trigger>
                  <span class="lm-chip lm-chip-all" aria-hidden="true">全</span>
                </template>
                全部（{{ totalCount }}）
              </n-tooltip>
            </template>
            <template v-if="!collapsed">全部</template>
            <template v-if="!collapsed" #suffix>
              <span class="lm-suffix">
                <span v-if="totalCount > 0" class="lm-count">{{ totalCount }}</span>
                <n-icon class="lm-chevron" :component="ChevronForwardOutline" :size="14" />
              </span>
            </template>
          </n-list-item>

          <n-list-item
            v-for="league in filteredLeagues"
            :key="league.league_id"
            class="lm-item"
            :class="{ active: selectedLeagueId === league.league_id }"
            @click="selectLeague(league.league_id)"
          >
            <template #prefix>
              <n-tooltip
                :disabled="!collapsed"
                placement="right"
              >
                <template #trigger>
                  <span
                    class="lm-chip"
                    :style="{
                      background: `${leagueTagColor(league.league_id)}18`,
                      color: leagueTagColor(league.league_id),
                    }"
                    aria-hidden="true"
                  >
                    {{ abbrOf(leagueLabel(league.league_name)) }}
                  </span>
                </template>
                {{ leagueLabel(league.league_name) }}
              </n-tooltip>
            </template>
            <template v-if="!collapsed">
              <n-ellipsis class="lm-name">
                {{ leagueLabel(league.league_name) }}
              </n-ellipsis>
            </template>
            <template v-if="!collapsed" #suffix>
              <span class="lm-suffix">
                <span v-if="countOf(league.league_id) > 0" class="lm-count">
                  {{ countOf(league.league_id) }}
                </span>
                <n-icon class="lm-chevron" :component="ChevronForwardOutline" :size="14" />
              </span>
            </template>
          </n-list-item>
        </n-list>

        <div
          v-if="!loading && !showAllRow && filteredLeagues.length === 0"
          class="lm-no-match"
        >
          无匹配联赛
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
  padding: 0 4px 12px;
  background: transparent;
}

.lm-item {
  padding: 8px 4px !important;
  margin: 2px 4px;
}

.lm-item :deep(.n-list-item__main) {
  min-width: 0;
}

.lm-name {
  display: block;
  min-width: 0;
  max-width: 100%;
}

.lm-item.active {
  color: var(--fa-accent);
  background: color-mix(in srgb, var(--fa-accent) 14%, transparent);
  font-weight: 600;
}

.league-menu.collapsed .lm-item :deep(.n-list-item__prefix) {
  margin-right: 0;
}

.lm-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--fa-radius-card);
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
}

.lm-chip-all {
  background: var(--fa-bg-soft);
  color: var(--fa-text-secondary);
}

.lm-item.active .lm-chip-all {
  color: inherit;
  background: color-mix(in srgb, var(--fa-accent) 10%, transparent);
}

.lm-suffix {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  min-width: 34px;
  color: var(--fa-text-muted);
  white-space: nowrap;
}

.lm-item.active .lm-suffix {
  color: inherit;
}

.lm-count {
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.lm-chevron {
  flex-shrink: 0;
  opacity: 0.65;
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
