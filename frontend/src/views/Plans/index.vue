<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { ChevronBackOutline, ChevronForwardOutline } from '@vicons/ionicons5'

import FavoriteDatesPicker from '@/views/Favorites/components/FavoriteDatesPicker.vue'
import { useBetPlans } from '@/composables/useBetPlans'
import { formatScheduleDay } from '@/utils/format'
import { todayDate } from '@/utils/homeDateStrip'
import type { SavedBetPlan } from '@/utils/betPlans'

defineOptions({ name: 'BetPlans' })

const FILTER_DATE_KEY = 'fa-bet-plans-filter-date'
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

function readSavedFilterDate(): string {
  try {
    const raw = localStorage.getItem(FILTER_DATE_KEY)
    if (raw && DATE_RE.test(raw)) return raw
  } catch {
    /* ignore */
  }
  return todayDate()
}

function writeSavedFilterDate(date: string) {
  try {
    localStorage.setItem(FILTER_DATE_KEY, date)
  } catch {
    /* ignore */
  }
}

const router = useRouter()
const message = useMessage()
const { planDays, plansForDay, reload, renamePlan, removePlan } = useBetPlans()

const filterDate = ref<string>(readSavedFilterDate())
const editingPlan = ref<SavedBetPlan | null>(null)
const renameDraft = ref('')
const showRename = ref(false)
watch(filterDate, writeSavedFilterDate)

const dayPlans = computed(() => plansForDay(filterDate.value))

function openPlan(id: string) {
  void router.push({ name: 'bet-plan-detail', params: { planId: id } })
}

function openRename(plan: SavedBetPlan) {
  editingPlan.value = plan
  renameDraft.value = plan.name
  showRename.value = true
}

async function confirmRename() {
  const current = editingPlan.value
  if (!current) return
  if (!(await renamePlan(current.id, renameDraft.value))) {
    message.warning('名称不能为空或保存失败')
    return
  }
  showRename.value = false
  editingPlan.value = null
  message.success('已改名')
}

async function confirmDelete(plan: SavedBetPlan) {
  try {
    await removePlan(plan.id)
  } catch {
    message.error('删除失败，请稍后重试')
    return
  }
  message.success('已删除')
}

function goBack() {
  void router.push({ name: 'mine' })
}

onMounted(() => {
  void reload()
})
</script>

<template>
  <div class="fa-page-frame">
    <div class="fa-page-shell plans-shell">
      <div class="plans-header fa-page-toolbar">
        <div class="plans-toolbar">
          <n-flex align="center" :size="8" style="min-width: 0;">
            <n-button size="small" quaternary aria-label="返回" @click="goBack">
              <template #icon>
                <n-icon :component="ChevronBackOutline" />
              </template>
            </n-button>
            <span class="plans-title">我的方案</span>
          </n-flex>
          <FavoriteDatesPicker
            v-model="filterDate"
            :marked-days="planDays"
            legend="当天有方案（赛程日）"
          />
        </div>
      </div>

      <n-scrollbar class="plans-scroll" trigger="hover">
        <div class="fa-page-content-padding plans-scroll-pad">
          <n-empty
            v-if="!dayPlans.length"
            :description="`${formatScheduleDay(filterDate)} 无保存方案`"
            class="plans-empty"
          />
          <n-list v-else hoverable clickable>
            <n-list-item
              v-for="plan in dayPlans"
              :key="plan.id"
              @click="openPlan(plan.id)"
            >
              <n-thing :title="plan.name">
                <template #header-extra>
                  <n-flex :size="10" align="center">
                    <n-flex :size="8" align="center" @click.stop>
                      <n-button size="tiny" tertiary @click="openRename(plan)">编辑</n-button>
                      <n-popconfirm @positive-click="confirmDelete(plan)">
                        <template #trigger>
                          <n-button size="tiny" type="error" tertiary>删除</n-button>
                        </template>
                        确定删除「{{ plan.name }}」？
                      </n-popconfirm>
                    </n-flex>
                    <n-icon
                      :component="ChevronForwardOutline"
                      :size="16"
                      depth="3"
                      aria-hidden="true"
                    />
                  </n-flex>
                </template>
              </n-thing>
            </n-list-item>
          </n-list>
        </div>
      </n-scrollbar>
    </div>

    <n-modal
      v-model:show="showRename"
      preset="dialog"
      title="修改方案名称"
      positive-text="保存"
      negative-text="取消"
      @positive-click="confirmRename"
    >
      <n-input
        v-model:value="renameDraft"
        maxlength="40"
        show-count
        placeholder="方案名称"
      />
    </n-modal>
  </div>
</template>

<style scoped>
.plans-shell {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--fa-bg);
}

.plans-header {
  flex-shrink: 0;
  width: 100%;
  max-width: var(--fa-mine-page-max-width);
  margin: 0 auto;
  box-sizing: border-box;
}

@media (max-width: 767px) {
  .plans-header {
    border-bottom: none;
  }
}

.plans-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.plans-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--fa-text-strong);
}

.plans-scroll {
  flex: 1;
  min-height: 0;
}

.plans-scroll-pad {
  max-width: var(--fa-mine-page-max-width);
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
  padding-top: 12px;
  padding-bottom: 24px;
}

.plans-empty {
  padding: 48px 0;
}
</style>
