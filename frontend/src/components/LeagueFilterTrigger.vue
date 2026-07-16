<script setup lang="ts">
import { FilterOutline } from '@vicons/ionicons5'
import { computed, ref, watch } from 'vue'

import type { LeagueFilterOption } from '@/api/leagues'
import { leagueNameZh } from '@/utils/leagueNames'

const props = withDefaults(
  defineProps<{
    options: LeagueFilterOption[]
    trackedIds: number[]
    iconOnly?: boolean
    filterActive?: boolean
    confirming?: boolean
  }>(),
  { iconOnly: false, filterActive: false, confirming: false },
)

const emit = defineEmits<{
  confirm: [ids: number[]]
}>()

const show = ref(false)
const draft = ref<number[]>([])

watch(show, (open) => {
  if (!open) return
  const available = new Set(props.options.map((o) => o.league_id))
  const preferred = props.trackedIds.filter((id) => available.has(id))
  if (preferred.length) {
    draft.value = preferred
    return
  }
  draft.value = props.options.filter((o) => o.default_checked).map((o) => o.league_id)
})

const configuredOptions = computed(() =>
  props.options.filter((o) => o.tier === 'configured'),
)

const extraOptions = computed(() =>
  props.options.filter((o) => o.tier === 'extra'),
)

function labelOf(opt: LeagueFilterOption): string {
  const name = leagueNameZh(opt.league_name)
  const n = opt.fixtures_count
  const suffix = n > 0 ? ` (${n})` : ''
  const tag = opt.tier === 'extra' && !opt.locally_loaded ? ' · 未入库' : ''
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

function confirm() {
  emit('confirm', [...draft.value])
  show.value = false
}
</script>

<template>
  <n-popover
    v-model:show="show"
    trigger="click"
    placement="bottom-end"
    :show-arrow="false"
  >
    <template #trigger>
      <n-tooltip :disabled="!iconOnly" placement="right">
        <template #trigger>
          <n-button
            size="tiny"
            quaternary
            class="league-filter-btn"
            :class="{ 'is-icon-only': iconOnly }"
            :type="filterActive ? 'primary' : 'default'"
            aria-label="筛选联赛"
          >
            <template #icon>
              <n-icon :component="FilterOutline" :size="14" />
            </template>
            <span v-if="!iconOnly">筛选</span>
          </n-button>
        </template>
        联赛筛选
      </n-tooltip>
    </template>
    <div class="league-filter-panel">
      <n-scrollbar style="max-height: min(360px, 55vh);">
        <n-checkbox-group v-model:value="draft">
          <div class="sections-row">
            <div class="section">
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
              <div class="section-title">其他联赛</div>
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
            </div>
          </div>
        </n-checkbox-group>
        <n-empty
          v-if="!options.length"
          description="今日暂无匹配联赛（可同步赛程后再试）"
          style="padding: 16px 0;"
        />
      </n-scrollbar>
      <n-space justify="end" class="actions" :size="8">
        <n-button
          size="tiny"
          quaternary
          :disabled="!configuredOptions.length"
          @click="selectConfigured"
        >
          仅配置
        </n-button>
        <n-button size="tiny" :disabled="!options.length" @click="selectAll">
          全选
        </n-button>
        <n-button size="tiny" :disabled="!options.length" @click="invertSelection">
          反选
        </n-button>
        <n-button
          size="tiny"
          type="primary"
          :loading="confirming"
          :disabled="!options.length"
          @click="confirm"
        >
          确认
        </n-button>
      </n-space>
    </div>
  </n-popover>
</template>

<style scoped>
.league-filter-btn.is-icon-only {
  width: 28px;
  height: 28px;
  padding: 0;
  justify-content: center;
}

.league-filter-panel {
  width: min(360px, 86vw);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sections-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.section {
  flex: 1;
  min-width: 0;
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
