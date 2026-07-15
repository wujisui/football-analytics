<script setup lang="ts">
import { FilterOutline } from '@vicons/ionicons5'
import { computed, ref, watch } from 'vue'

export type ResultsHitKey = 'result' | 'score' | 'ou' | 'btts'

export interface ResultsLeagueOption {
  league_id: number
  label: string
}

const HIT_OPTIONS: { key: ResultsHitKey; label: string }[] = [
  { key: 'score', label: '比分' },
  { key: 'result', label: '胜平负' },
  { key: 'ou', label: '大小球' },
  { key: 'btts', label: '双方进球' },
]

const props = withDefaults(
  defineProps<{
    leagueOptions: ResultsLeagueOption[]
    selectedLeagueIds: number[]
    selectedHitKeys: ResultsHitKey[]
    filterActive?: boolean
  }>(),
  { filterActive: false },
)

const emit = defineEmits<{
  confirm: [payload: { leagueIds: number[]; hitKeys: ResultsHitKey[] }]
}>()

const show = ref(false)
const draftLeagues = ref<number[]>([])
const draftHits = ref<ResultsHitKey[]>([])

const allLeagueIds = computed(() => props.leagueOptions.map((o) => o.league_id))
const allHitKeys = computed(() => HIT_OPTIONS.map((o) => o.key))

watch(show, (open) => {
  if (!open) return
  const allow = new Set(allLeagueIds.value)
  draftLeagues.value = props.selectedLeagueIds.filter((id) => allow.has(id))
  if (!draftLeagues.value.length) {
    draftLeagues.value = [...allLeagueIds.value]
  }
  draftHits.value = props.selectedHitKeys.length
    ? [...props.selectedHitKeys]
    : [...allHitKeys.value]
})

function selectAll() {
  draftLeagues.value = [...allLeagueIds.value]
  draftHits.value = [...allHitKeys.value]
}

function confirm() {
  emit('confirm', {
    leagueIds: [...draftLeagues.value],
    hitKeys: [...draftHits.value],
  })
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
        :type="filterActive ? 'primary' : 'default'"
        aria-label="筛选赛果"
      >
        <template #icon>
          <n-icon :component="FilterOutline" :size="14" />
        </template>
        筛选
      </n-button>
    </template>
    <div class="results-filter-panel">
      <p class="hint">
        联赛与预测维度均可多选；<strong>默认全部勾选</strong>。取消勾选即从列表中隐藏。
      </p>
      <n-scrollbar style="max-height: min(360px, 55vh);">
        <div class="sections-row">
          <div class="section">
            <div class="section-title">联赛名称</div>
            <n-checkbox-group v-model:value="draftLeagues">
              <n-space vertical :size="6">
                <n-checkbox
                  v-for="opt in leagueOptions"
                  :key="opt.league_id"
                  :value="opt.league_id"
                  :label="opt.label"
                />
              </n-space>
            </n-checkbox-group>
            <n-empty
              v-if="!leagueOptions.length"
              description="当日暂无联赛"
              style="padding: 8px 0;"
            />
          </div>
          <div class="section">
            <div class="section-title">预测结果</div>
            <n-checkbox-group v-model:value="draftHits">
              <n-space vertical :size="6">
                <n-checkbox
                  v-for="opt in HIT_OPTIONS"
                  :key="opt.key"
                  :value="opt.key"
                  :label="opt.label"
                />
              </n-space>
            </n-checkbox-group>
          </div>
        </div>
      </n-scrollbar>
      <n-space justify="end" :size="8" class="actions">
        <n-button size="tiny" :disabled="!leagueOptions.length" @click="selectAll">
          全选
        </n-button>
        <n-button
          size="tiny"
          type="primary"
          :disabled="!leagueOptions.length"
          @click="confirm"
        >
          确认
        </n-button>
      </n-space>
    </div>
  </n-popover>
</template>

<style scoped>
.results-filter-panel {
  width: min(360px, 86vw);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--fa-text-muted);
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
