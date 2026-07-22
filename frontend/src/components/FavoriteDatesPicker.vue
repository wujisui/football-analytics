<script setup lang="ts">
import { nextTick, onBeforeUnmount, watch } from 'vue'

const filterDate = defineModel<string | null>({ required: true })

const props = withDefaults(
  defineProps<{
    favoriteDays: ReadonlySet<string>
    placeholder?: string
  }>(),
  { placeholder: '按赛程日筛选（同首页）' },
)

let markTimer: ReturnType<typeof setTimeout> | null = null
let panelObserver: MutationObserver | null = null

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

function parsePanelMonthYear(panel: HTMLElement): { year: number; month: number } | null {
  const text = panel.querySelector('.n-date-panel-month__text')?.textContent?.trim()
  if (!text) return null
  const yearMatch = text.match(/(\d{4})/)
  const monthMatch = text.match(/(\d{1,2})\s*月/)
  if (!yearMatch || !monthMatch) return null
  const year = Number(yearMatch[1])
  const month = Number(monthMatch[1])
  if (!Number.isFinite(year) || !Number.isFinite(month)) return null
  return { year, month }
}

function cellDayKey(cell: HTMLElement, year: number, month: number): string {
  const day = Number.parseInt(cell.textContent?.trim() || '', 10)
  if (!Number.isFinite(day)) return ''
  let y = year
  let m = month
  if (cell.classList.contains('n-date-panel-date--excluded')) {
    if (day > 20) {
      m -= 1
      if (m < 1) {
        m = 12
        y -= 1
      }
    } else if (day < 15) {
      m += 1
      if (m > 12) {
        m = 1
        y += 1
      }
    }
  }
  return `${y}-${pad2(m)}-${pad2(day)}`
}

function markPanels() {
  for (const panel of document.querySelectorAll('.n-date-panel')) {
    const parsed = parsePanelMonthYear(panel as HTMLElement)
    if (!parsed) continue
    for (const cell of panel.querySelectorAll('.n-date-panel-date')) {
      const el = cell as HTMLElement
      const key = cellDayKey(el, parsed.year, parsed.month)
      const hasFavorite = !!key && props.favoriteDays.has(key)
      el.classList.toggle('fa-date-has-favorite', hasFavorite)

      let mark = el.querySelector('.fa-date-favorite-mark')
      if (hasFavorite) {
        if (!mark) {
          mark = document.createElement('span')
          mark.className = 'fa-date-favorite-mark'
          mark.setAttribute('aria-hidden', 'true')
          el.appendChild(mark)
        }
      } else {
        mark?.remove()
      }
    }
  }
}

function scheduleMark() {
  if (markTimer) clearTimeout(markTimer)
  markTimer = setTimeout(() => {
    markTimer = null
    void nextTick(markPanels)
  }, 0)
}

function stopPanelObserver() {
  panelObserver?.disconnect()
  panelObserver = null
}

function startPanelObserver() {
  stopPanelObserver()
  const panel = document.querySelector('.n-date-panel')
  if (!panel) return
  panelObserver = new MutationObserver(scheduleMark)
  panelObserver.observe(panel, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['class'],
  })
}

function onPanelShow(open: boolean) {
  if (!open) {
    stopPanelObserver()
    return
  }
  scheduleMark()
  void nextTick(startPanelObserver)
}

watch(() => props.favoriteDays, scheduleMark)

onBeforeUnmount(() => {
  if (markTimer) clearTimeout(markTimer)
  stopPanelObserver()
  for (const cell of document.querySelectorAll('.n-date-panel-date.fa-date-has-favorite')) {
    cell.classList.remove('fa-date-has-favorite')
    cell.querySelector('.fa-date-favorite-mark')?.remove()
  }
})
</script>

<template>
  <n-date-picker
    v-model:formatted-value="filterDate"
    value-format="yyyy-MM-dd"
    type="date"
    size="small"
    clearable
    :placeholder="placeholder"
    class="favorite-dates-picker"
    @update:show="onPanelShow"
    @prev-month="scheduleMark"
    @next-month="scheduleMark"
    @prev-year="scheduleMark"
    @next-year="scheduleMark"
  >
    <template #footer>
      <div class="favorite-date-legend">
        <span class="favorite-date-dot" aria-hidden="true" />
        当天有收藏（赛程日）
      </div>
    </template>
  </n-date-picker>
</template>

<style scoped>
.favorite-dates-picker {
  flex: 1;
  min-width: 0;
}

.favorite-date-legend {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--fa-text-secondary);
}

.favorite-date-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--fa-highlight-text);
  flex-shrink: 0;
}
</style>

<style>
/* 不用 ::after：会与 Naive UI 选中态背景伪元素冲突，导致日期数字不可见 */
.n-date-panel-date .fa-date-favorite-mark {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background-color: var(--fa-highlight-text);
  pointer-events: none;
  z-index: 1;
}

.n-date-panel-date.fa-date-has-favorite.n-date-panel-date--selected .fa-date-favorite-mark {
  background-color: var(--n-panel-color, #fff);
}
</style>
