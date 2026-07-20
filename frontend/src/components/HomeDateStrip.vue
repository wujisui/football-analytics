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

function setTabRef(iso: string, el: HTMLElement | null) {
  if (el) tabRefs.set(iso, el)
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
    <button
      v-for="tab in tabs"
      :key="tab.iso"
      :ref="(el) => setTabRef(tab.iso, el as HTMLElement | null)"
      type="button"
      role="tab"
      class="date-tab"
      :class="{ active: selected === tab.iso, disabled: isDisabled(tab.iso) }"
      :aria-selected="selected === tab.iso"
      :disabled="isDisabled(tab.iso)"
      @click="selectTab(tab.iso)"
    >
      <span class="tab-top">{{ tab.topLabel }}</span>
      <span class="tab-bottom">{{ tab.bottomLabel }}</span>
    </button>
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
  appearance: none;
  flex: 0 0 auto;
  min-width: 54px;
  padding: 6px 10px 5px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--fa-text-secondary);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.date-tab:hover:not(.active):not(.disabled) {
  background: color-mix(in srgb, var(--fa-text) 6%, transparent);
  color: var(--fa-text);
}

.date-tab.active {
  background: color-mix(in srgb, var(--n-primary-color, #18a058) 16%, transparent);
  color: var(--n-primary-color, #18a058);
}

.date-tab.active .tab-bottom {
  font-weight: 700;
}

.date-tab.disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.date-tab.disabled:hover {
  background: transparent;
  color: var(--fa-text-secondary);
}

.date-tab:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--n-primary-color, #18a058) 45%, transparent);
  outline-offset: 1px;
}

.tab-top {
  font-size: 12px;
  line-height: 1.2;
  white-space: nowrap;
}

.tab-bottom {
  font-size: 13px;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
</style>
