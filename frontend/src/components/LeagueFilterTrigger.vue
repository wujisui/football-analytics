<script setup lang="ts">
import { FilterOutline } from '@vicons/ionicons5'
import { computed, ref, watch } from 'vue'

import type { LeagueFilterOption } from '@/api/leagues'
import { leagueLabel } from '@/utils/leagueNames'

const props = withDefaults(
  defineProps<{
    options: LeagueFilterOption[]
    trackedIds: number[]
    iconOnly?: boolean
    filterActive?: boolean
    confirming?: boolean
    /** 赛果页：仅展示完场联赛，隐藏「未入库」标记与配置分区。 */
    finishedMode?: boolean
    /** Mobile drawer: modal + stacked layout so content is not clipped. */
    drawerMode?: boolean
  }>(),
  { iconOnly: false, filterActive: false, confirming: false, finishedMode: false, drawerMode: false },
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
  props.finishedMode ? [] : props.options.filter((o) => o.tier === 'configured'),
)

const extraOptions = computed(() =>
  props.finishedMode ? props.options : props.options.filter((o) => o.tier === 'extra'),
)

const extraSectionTitle = computed(() =>
  props.finishedMode ? '完场联赛' : '其他联赛',
)

function labelOf(opt: LeagueFilterOption): string {
  const name = leagueLabel(opt.league_name)
  const n = opt.fixtures_count
  const suffix = n > 0 ? ` (${n})` : ''
  const tag = opt.tier === 'extra' && !opt.locally_loaded && !props.finishedMode ? ' · 未入库' : ''
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
  <template v-if="drawerMode">
    <n-tooltip :disabled="!iconOnly" placement="right-end">
      <template #trigger>
        <n-button
          size="tiny"
          quaternary
          class="league-filter-btn"
          :class="{ 'is-icon-only': iconOnly }"
          :type="filterActive ? 'primary' : 'default'"
          aria-label="筛选联赛"
          @click="show = true"
        >
          <template #icon>
            <n-icon :component="FilterOutline" :size="14" />
          </template>
          <span v-if="!iconOnly">筛选</span>
        </n-button>
      </template>
      联赛筛选
    </n-tooltip>

    <n-modal
      v-model:show="show"
      preset="card"
      title="联赛筛选"
      :style="{ width: 'min(420px, 92vw)' }"
      :segmented="{ content: true, footer: true }"
    >
      <div class="league-filter-panel drawer-mode">
        <n-scrollbar style="max-height: min(420px, 62vh);">
          <n-checkbox-group v-model:value="draft">
            <div class="sections-row stacked">
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
      </div>
      <template #footer>
        <n-space justify="end" class="actions" :size="8">
          <n-button
            v-if="!finishedMode"
            size="small"
            quaternary
            :disabled="!configuredOptions.length"
            @click="selectConfigured"
          >
            仅配置
          </n-button>
          <n-button size="small" :disabled="!options.length" @click="selectAll">
            全选
          </n-button>
          <n-button size="small" :disabled="!options.length" @click="invertSelection">
            反选
          </n-button>
          <n-button
            size="small"
            type="primary"
            :loading="confirming"
            :disabled="!options.length"
            @click="confirm"
          >
            确认
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </template>

  <n-popover
    v-else
    v-model:show="show"
    trigger="click"
    placement="right-start"
    :show-arrow="false"
    to="body"
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
