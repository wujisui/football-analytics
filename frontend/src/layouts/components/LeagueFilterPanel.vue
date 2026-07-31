<script setup lang="ts">
import { computed } from 'vue'

import type { LeagueFilterOption } from '@/api/leagues'
import { leagueLabel } from '@/utils/leagueNames'

const props = withDefaults(
  defineProps<{
    options: LeagueFilterOption[]
    stacked?: boolean
    compactActions?: boolean
  }>(),
  {
    stacked: false,
    compactActions: false,
  },
)

const draft = defineModel<number[]>('draft', { required: true })

const emit = defineEmits<{
  confirm: []
}>()

const configuredOptions = computed(() =>
  props.options.filter((o) => o.tier === 'configured'),
)

const extraOptions = computed(() =>
  props.options.filter((o) => o.tier === 'extra'),
)

const actionSize = computed(() => (props.compactActions ? 'tiny' : 'small'))
const listMaxHeight = computed(() =>
  props.stacked ? 'min(420px, 62vh)' : 'min(360px, 55vh)',
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
          <div class="section-title">热门</div>
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
          <div class="section-title">其他</div>
          <n-scrollbar class="section-scroll">
            <n-space vertical :size="6">
              <n-checkbox
                v-for="opt in extraOptions"
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
}

.filter-body {
  min-height: 0;
}

.sections-row {
  display: flex;
  align-items: stretch;
  gap: 16px;
  min-height: 0;
}

.sections-row.stacked {
  flex-direction: column;
  gap: 14px;
}

.section {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.section-title {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--fa-text-muted);
  margin-bottom: 6px;
  padding-bottom: 2px;
  background: var(--n-color, var(--fa-bg-elevated));
}

.section-scroll {
  flex: 1;
  min-height: 0;
}

.section-scroll :deep(.n-scrollbar-container) {
  max-height: 100%;
}

.actions {
  margin-top: 2px;
  flex-shrink: 0;
}
</style>
