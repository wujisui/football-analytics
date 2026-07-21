<script setup lang="ts">
import { computed } from 'vue'

import type { LeagueFilterOption } from '@/api/leagues'
import { leagueLabel } from '@/utils/leagueNames'

const props = withDefaults(
  defineProps<{
    options: LeagueFilterOption[]
    finishedMode?: boolean
    stacked?: boolean
    compactActions?: boolean
    confirming?: boolean
  }>(),
  {
    finishedMode: false,
    stacked: false,
    compactActions: false,
    confirming: false,
  },
)

const draft = defineModel<number[]>('draft', { required: true })

const emit = defineEmits<{
  confirm: []
}>()

const configuredOptions = computed(() =>
  props.finishedMode ? [] : props.options.filter((o) => o.tier === 'configured'),
)

const extraOptions = computed(() =>
  props.finishedMode ? props.options : props.options.filter((o) => o.tier === 'extra'),
)

const extraSectionTitle = computed(() =>
  props.finishedMode ? '完场联赛' : '其他联赛',
)

const actionSize = computed(() => (props.compactActions ? 'tiny' : 'small'))

function labelOf(opt: LeagueFilterOption): string {
  const name = leagueLabel(opt.league_name)
  const n = opt.fixtures_count
  const suffix = n > 0 ? ` (${n})` : ''
  const tag =
    opt.tier === 'extra' && !opt.locally_loaded && !props.finishedMode ? ' · 未入库' : ''
  return `${name}${suffix}${tag}`
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
    <n-scrollbar :style="{ maxHeight: stacked ? 'min(420px, 62vh)' : 'min(360px, 55vh)' }">
      <n-checkbox-group v-model:value="draft">
        <div class="sections-row" :class="{ stacked }">
          <div v-if="!finishedMode" class="section">
            <div class="section-title">联赛</div>
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
              description="暂无配置联赛"
              style="padding: 8px 0;"
            />
          </div>
          <div class="section">
            <div class="section-title">{{ extraSectionTitle }}</div>
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
              :description="finishedMode ? '当日暂无完场联赛' : '暂无其他联赛'"
              style="padding: 8px 0;"
            />
          </div>
        </div>
      </n-checkbox-group>
      <n-empty
        v-if="!options.length"
        :description="finishedMode ? '当日暂无完场赛果' : '今日暂无匹配联赛（可同步赛程后再试）'"
        style="padding: 16px 0;"
      />
    </n-scrollbar>
    <n-space justify="end" class="actions" :size="8">
      <n-button
        v-if="!finishedMode"
        :size="actionSize"
        quaternary
        :disabled="!configuredOptions.length"
        @click="selectConfigured"
      >
        仅配置
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
        :loading="confirming"
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

.sections-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.sections-row.stacked {
  flex-direction: column;
  gap: 14px;
}

.section {
  flex: 1;
  min-width: 0;
  width: 100%;
}

.section-title {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--fa-text-muted);
  margin-bottom: 6px;
}

.actions {
  margin-top: 2px;
}
</style>
