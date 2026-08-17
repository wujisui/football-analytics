<script setup lang="ts">
import { SearchOutline } from '@vicons/ionicons5'
import { computed, ref, watch } from 'vue'

import type { LeagueFilterOption } from '@/api/leagues'
import { fuzzyMatchAny } from '@/utils/fuzzySearch'
import { leagueLabel } from '@/utils/leagueNames'

const props = withDefaults(
  defineProps<{
    options: LeagueFilterOption[]
    stacked?: boolean
    compactActions?: boolean
    /** 弹层打开时清空「其他」搜索，避免上次关键词残留 */
    visible?: boolean
  }>(),
  {
    stacked: false,
    compactActions: false,
    visible: false,
  },
)

const draft = defineModel<number[]>('draft', { required: true })

const emit = defineEmits<{
  confirm: []
}>()

const extraQuery = ref('')

watch(
  () => props.visible,
  (open) => {
    if (open) extraQuery.value = ''
  },
)

const configuredOptions = computed(() =>
  props.options.filter((o) => o.tier === 'configured'),
)

const extraOptions = computed(() =>
  props.options.filter((o) => o.tier === 'extra'),
)

const filteredExtraOptions = computed(() => {
  const q = extraQuery.value.trim()
  if (!q) return extraOptions.value
  return extraOptions.value.filter((opt) =>
    fuzzyMatchAny(q, [leagueLabel(opt.league_name), opt.league_name, opt.country]),
  )
})

const actionSize = computed(() => (props.compactActions ? 'tiny' : 'small'))
const listMaxHeight = computed(() =>
  props.stacked ? undefined : 'min(360px, 55vh)',
)

function labelOf(opt: LeagueFilterOption): string {
  const name = leagueLabel(opt.league_name)
  const n = opt.fixtures_count
  const suffix = n > 0 ? ` (${n})` : ''
  return `${name}${suffix}`
}

function selectConfigured() {
  draft.value = configuredOptions.value.map((o) => o.league_id)
}

function selectAll() {
  draft.value = props.options.map((o) => o.league_id)
}

function invertSelection() {
  const selected = new Set(draft.value)
  draft.value = props.options
    .map((o) => o.league_id)
    .filter((id) => !selected.has(id))
}
</script>

<template>
  <div class="league-filter-panel" :class="{ 'drawer-mode': stacked }">
    <n-checkbox-group v-model:value="draft" class="filter-body">
      <div
        class="sections-row"
        :class="{ stacked }"
        :style="{ maxHeight: listMaxHeight }"
      >
        <div class="section">
          <div class="section-head">
            <div class="section-title">热门</div>
          </div>
          <n-scrollbar class="section-scroll">
            <n-space vertical :size="6">
              <n-checkbox
                v-for="opt in configuredOptions"
                :key="opt.league_id"
                :value="opt.league_id"
                :label="labelOf(opt)"
              />
            </n-space>
            <n-empty
              v-if="!configuredOptions.length"
              description="暂无热门联赛"
              style="padding: 8px 0;"
            />
          </n-scrollbar>
        </div>
        <div class="section">
          <div class="section-head">
            <div class="section-title">其他</div>
            <n-input
              v-if="extraOptions.length"
              v-model:value="extraQuery"
              class="extra-search"
              size="tiny"
              placeholder="搜索"
              clearable
            >
              <template #prefix>
                <n-icon :component="SearchOutline" :size="13" />
              </template>
            </n-input>
          </div>
          <n-scrollbar class="section-scroll">
            <n-space vertical :size="6">
              <n-checkbox
                v-for="opt in filteredExtraOptions"
                :key="opt.league_id"
                :value="opt.league_id"
                :label="labelOf(opt)"
              />
            </n-space>
            <n-empty
              v-if="!extraOptions.length"
              description="暂无其他联赛"
              style="padding: 8px 0;"
            />
            <n-empty
              v-else-if="!filteredExtraOptions.length"
              description="无匹配联赛"
              style="padding: 8px 0;"
            />
          </n-scrollbar>
        </div>
      </div>
    </n-checkbox-group>
    <n-empty
      v-if="!options.length"
      description="今日暂无匹配联赛（可同步赛程后再试）"
      style="padding: 16px 0;"
    />
    <n-space justify="end" class="actions" :size="8">
      <n-button
        :size="actionSize"
        quaternary
        :disabled="!configuredOptions.length"
        @click="selectConfigured"
      >
        仅热门
      </n-button>
      <n-button :size="actionSize" :disabled="!options.length" @click="selectAll">
        全选
      </n-button>
      <n-button :size="actionSize" :disabled="!options.length" @click="invertSelection">
        反选
      </n-button>
      <n-button
        :size="actionSize"
        type="primary"
        :disabled="!options.length"
        @click="emit('confirm')"
      >
        确认
      </n-button>
    </n-space>
  </div>
</template>

<style scoped>
.league-filter-panel {
  width: min(360px, 86vw);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.league-filter-panel.drawer-mode {
  width: 100%;
  height: min(520px, calc(100dvh - 180px));
  max-height: 100%;
  overflow: hidden;
}

.filter-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.sections-row {
  flex: 1;
  display: flex;
  align-items: stretch;
  gap: 16px;
  width: 100%;
  min-height: 0;
  overflow: hidden;
}

.sections-row.stacked {
  /* Mobile modal: two fixed columns with independently scrolling lists. */
  flex-direction: row;
  gap: 10px;
}

.section {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 标题与「其他」搜索框同一行，两列表头等高 */
.section-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 24px;
  margin-bottom: 6px;
  padding-bottom: 2px;
  background: var(--n-color, var(--fa-bg-elevated));
}

.section-title {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--fa-text-muted);
}

.extra-search {
  flex: 1;
  min-width: 0;
  margin-left: auto;
}

.section-scroll {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.section-scroll :deep(.n-scrollbar-container) {
  height: 100%;
  max-height: 100%;
}

.section-scroll :deep(.n-scrollbar-content) {
  padding-right: 4px;
}

.section-scroll :deep(.n-checkbox) {
  width: 100%;
  align-items: flex-start;
}

.section-scroll :deep(.n-checkbox__label) {
  min-width: 0;
  padding-right: 2px;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.35;
}

.actions {
  margin-top: 2px;
  flex-shrink: 0;
}

@media (max-width: 767px) {
  .league-filter-panel {
    gap: 12px;
  }

  .section-head {
    margin-bottom: 8px;
    padding: 0 2px 6px;
    border-bottom: 1px solid var(--fa-border);
  }

  .section-title {
    font-size: 12px;
  }

  .actions {
    width: 100%;
    flex-wrap: nowrap !important;
  }

  .actions :deep(.n-space) {
    flex-wrap: nowrap !important;
  }
}
</style>
