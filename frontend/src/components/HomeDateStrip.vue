<script setup lang="ts">
import { computed, nextTick, onMounted, watch } from 'vue'

import { buildHomeDateTabs, clampToLatest, clampToToday, todayDate } from '@/utils/homeDateStrip'

const selected = defineModel<string>({ required: true })

const props = withDefaults(
  defineProps<{
    /** Prematch pages: cannot pick dates before today. */
    disableBeforeToday?: boolean
    /** Results page: cannot pick dates after today. */
    disableAfterToday?: boolean
  }>(),
  { disableBeforeToday: false, disableAfterToday: false },
)

const tabRefs = new Map<string, HTMLElement>()

const today = computed(() => todayDate())
const tabs = computed(() => buildHomeDateTabs(today.value))

function setTabRef(iso: string, el: unknown) {
  const node =
    el && typeof el === 'object' && '$el' in el
      ? ((el as { $el: HTMLElement }).$el as HTMLElement)
      : (el as HTMLElement | null)
  if (node instanceof HTMLElement) tabRefs.set(iso, node)
  else tabRefs.delete(iso)
}

function isDisabled(iso: string): boolean {
  if (props.disableBeforeToday && iso < today.value) return true
  if (props.disableAfterToday && iso > today.value) return true
  return false
}

function selectTab(iso: string) {
  if (isDisabled(iso)) return
  selected.value = iso
}

function tabType(iso: string) {
  return selected.value === iso ? 'primary' : 'default'
}

async function scrollActiveIntoView(behavior: ScrollBehavior = 'smooth') {
  await nextTick()
  tabRefs.get(selected.value)?.scrollIntoView({
    inline: 'center',
    block: 'nearest',
    behavior,
  })
}

watch(
  () => selected.value,
  () => {
    void scrollActiveIntoView()
  },
)

watch(
  () =>
    [props.disableBeforeToday, props.disableAfterToday, selected.value] as const,
  ([disablePast, disableFuture, day]) => {
    let next = day
    if (disablePast && next < today.value) {
      next = clampToToday(next, today.value)
    }
    if (disableFuture && next > today.value) {
      next = clampToLatest(next, today.value)
    }
    if (next !== selected.value) selected.value = next
  },
  { immediate: true },
)

onMounted(() => {
  void scrollActiveIntoView('auto')
})
</script>

<template>
  <div class="date-strip" role="tablist" aria-label="赛程日期">
    <n-button
      v-for="tab in tabs"
      :key="tab.iso"
      :ref="(el) => setTabRef(tab.iso, el)"
      size="small"
      role="tab"
      class="date-tab"
      :type="tabType(tab.iso)"
      :secondary="selected === tab.iso"
      :quaternary="selected !== tab.iso"
      :aria-selected="selected === tab.iso"
      :disabled="isDisabled(tab.iso)"
      @click="selectTab(tab.iso)"
    >
      <span class="tab-stack">
        <span class="tab-top">{{ tab.topLabel }}</span>
        <span class="tab-bottom">{{ tab.bottomLabel }}</span>
      </span>
    </n-button>
  </div>
</template>

<style scoped>
.date-strip {
  display: flex;
  align-items: stretch;
  gap: 6px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 4px 2px 8px;
  margin: 0 -2px;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.date-strip::-webkit-scrollbar {
  display: none;
}

.date-tab {
  flex: 0 0 auto;
  height: auto;
  padding: 4px 10px;
}

.tab-stack {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  line-height: 1.2;
}

.tab-top {
  font-size: 12px;
  white-space: nowrap;
}

.tab-bottom {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.date-tab.n-button--primary-type .tab-bottom,
.date-tab.n-button--primary-type.n-button--secondary .tab-bottom {
  font-weight: 700;
}
</style>
