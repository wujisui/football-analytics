<script setup lang="ts">
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
      <n-button
        size="tiny"
        quaternary
        class="league-filter-btn"
        :class="{ 'is-icon-only': iconOnly }"
        :type="filterActive ? 'primary' : 'default'"
        :title="iconOnly ? '联赛筛选' : undefined"
        aria-label="筛选联赛"
      >
        <template #icon>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            width="14"
            height="14"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M3 5h18l-7 8v5l-4 2v-7L3 5z" />
          </svg>
        </template>
        <span v-if="!iconOnly">筛选</span>
      </n-button>
    </template>
    <div class="league-filter-panel">
      <n-scrollbar style="max-height: min(360px, 55vh);">
        <n-checkbox-group v-model:value="draft">
          <n-flex :size="[10, 6]" :wrap="true">
            <n-checkbox
              v-for="opt in options"
              :key="opt.league_id"
              :value="opt.league_id"
              :label="labelOf(opt)"
            />
          </n-flex>
        </n-checkbox-group>
        <n-empty
          v-if="!options.length"
          description="今日暂无匹配联赛（可强制刷新后再试）"
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
  width: min(340px, 86vw);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.actions {
  margin-top: 2px;
}
</style>
