<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import FixtureList from '@/components/FixtureList.vue'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useTrackedLeagues } from '@/composables/useTrackedLeagues'
import { parseApiDate } from '@/utils/format'

defineOptions({ name: 'Predictions' })

const isPhone = useIsPhone()
const { LOOKAHEAD_DAYS, allFixtures, windowLabel, loading, error, loadHomeFixtures } =
  useHomeFixtures()
const { trackedIds, loadFilterOptions } = useTrackedLeagues()

const selectedDay = ref<string | null>(null)
const listShellRef = ref<HTMLElement | null>(null)

/** Scroll container for n-back-top (n-scrollbar internals). */
function listScrollListenTo(): HTMLElement {
  return (
    (listShellRef.value?.querySelector(
      '.n-scrollbar-container',
    ) as HTMLElement | null) ?? document.documentElement
  )
}

const trackedIdSet = computed(() => new Set(trackedIds.value))
const ACTIVE_STATUSES = new Set(['pending', 'live'])

function isActiveFixture(status: string): boolean {
  return ACTIVE_STATUSES.has(status.toLowerCase())
}

function localDayKey(iso: string): string {
  const d = parseApiDate(iso)
  if (Number.isNaN(d.getTime())) return String(iso).slice(0, 10)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const trackedFixtures = computed(() =>
  allFixtures.value.filter(
    (f) => trackedIdSet.value.has(f.league_id) && isActiveFixture(f.status),
  ),
)

const availableDayKeys = computed(() => {
  const keys = new Set<string>()
  for (const f of trackedFixtures.value) keys.add(localDayKey(f.fixture_date))
  return keys
})

const displayedFixtures = computed(() => {
  let list = trackedFixtures.value
  if (selectedDay.value) {
    list = list.filter((f) => localDayKey(f.fixture_date) === selectedDay.value)
  }
  return list
    .slice()
    .sort(
      (a, b) =>
        parseApiDate(a.fixture_date).getTime() -
        parseApiDate(b.fixture_date).getTime(),
    )
})

function isDayDisabled(ts: number): boolean {
  const d = new Date(ts)
  const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return !availableDayKeys.value.has(key)
}

const emptyText = computed(() => {
  if (!trackedIds.value.length) return '请先在赛前页「筛选」中勾选联赛'
  if (selectedDay.value && !displayedFixtures.value.length) {
    return `${selectedDay.value} 暂无预测`
  }
  return `近 ${LOOKAHEAD_DAYS} 日暂无未完赛预测`
})

const listPad = computed(() =>
  isPhone.value ? '12px 12px 20px' : '16px 20px 24px',
)

onMounted(async () => {
  try {
    await Promise.all([loadFilterOptions(), loadHomeFixtures()])
  } catch {
    // error already set
  }
})
</script>

<template>
  <!-- Lock height like Home: toolbar stays put; only the list scrolls. -->
  <n-layout
    class="pred-layout"
    position="absolute"
    content-style="display: flex; flex-direction: column; height: 100%; overflow: hidden;"
  >
    <n-layout-header bordered class="pred-toolbar" style="flex-shrink: 0;">
      <div class="pred-shell">
        <n-page-header title="预测列表" class="page-header">
          <template #subtitle>
            <span v-if="windowLabel" class="window-meta">{{ windowLabel }}</span>
            <span class="window-meta">{{ displayedFixtures.length }} 场</span>
          </template>
          <template #extra>
            <n-date-picker
              v-model:formatted-value="selectedDay"
              value-format="yyyy-MM-dd"
              type="date"
              size="small"
              clearable
              placeholder="全部日期"
              :is-date-disabled="isDayDisabled"
            />
          </template>
        </n-page-header>
      </div>
    </n-layout-header>

    <div ref="listShellRef" class="pred-list-shell">
      <n-scrollbar
        class="pred-list-scroll"
        trigger="hover"
        :content-style="`padding: ${listPad}; box-sizing: border-box;`"
      >
        <div class="pred-shell">
          <n-alert v-if="error" type="error" :title="error" class="state">
            <n-button size="small" type="primary" @click="loadHomeFixtures({ force: true })">
              重试
            </n-button>
          </n-alert>
          <n-spin v-else :show="loading && !allFixtures.length">
            <FixtureList
              v-if="!loading || allFixtures.length"
              mode="prediction"
              :fixtures="displayedFixtures"
              :empty-description="emptyText"
            />
          </n-spin>
        </div>
      </n-scrollbar>
      <n-back-top
        v-if="listShellRef"
        class="pred-back-top"
        :to="listShellRef"
        :listen-to="listScrollListenTo"
        :visibility-height="240"
        :right="16"
        :bottom="20"
      />
    </div>
  </n-layout>
</template>

<style scoped>
.pred-layout {
  inset: 0;
  height: 100%;
  background: var(--fa-bg);
}

.pred-toolbar {
  height: auto;
  padding: 10px 12px 8px;
  background: var(--fa-bg-elevated);
  flex-shrink: 0;
  position: relative;
  z-index: 2;
}

/* Keep prediction cards at a readable column width on wide screens. */
.pred-shell {
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
}

.page-header {
  margin-top: 0;
}

.window-meta + .window-meta::before {
  content: ' · ';
  color: var(--fa-text-faint);
}

.pred-list-shell {
  flex: 1;
  min-height: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  background: var(--fa-bg);
}

.pred-list-scroll {
  flex: 1;
  min-height: 0;
  height: 100%;
}

/* Keep back-top inside the list pane (not viewport-fixed far right). */
.pred-list-shell :deep(.pred-back-top) {
  position: absolute !important;
}

.state {
  margin-bottom: 12px;
}

@media (min-width: 768px) {
  .pred-toolbar {
    padding: 12px 20px 10px;
  }
}
</style>
