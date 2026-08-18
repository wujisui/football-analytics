<script setup lang="ts">
import {computed, h, onMounted, ref} from 'vue'
import {NInput, useMessage, useModal, type ModalReactive} from 'naive-ui'
import {ChevronForwardOutline} from '@vicons/ionicons5'

import PlanDetail from '@/views/Mine/plans/PlanDetail.vue'
import {useAuthSession} from '@/composables/useAuthSession'
import {useBetPlans} from '@/composables/useBetPlans'
import {useIsPhone} from '@/composables/useMediaQuery'
import {formatScheduleDay, parseApiDate} from '@/utils/format'
import type {SavedBetPlan} from '@/utils/betPlans'
import FavoriteDatesPicker from '@/views/Favorites/components/FavoriteDatesPicker.vue'

defineOptions({name: 'BetPlans'})

const message = useMessage()
const modal = useModal()
const isPhone = useIsPhone()
const {requireLogin} = useAuthSession()
const {
  filterDate,
  plansForDay,
  ensureLoaded,
  renamePlan,
  removePlan,
  getPlan,
  planDays
} = useBetPlans()

const dayPlans = computed(() => plansForDay(filterDate.value))
const dayPlanCountLabel = computed(
    () => `已保存 ${plansForDay(filterDate.value).length} 个方案`,
)

let detailModal: ModalReactive | null = null
let detailPlanId: string | null = null

/** yyyy-MM-dd HH:mm in local timezone. */
function formatPlanSavedAt(savedAt: string): string {
  const d = parseApiDate(savedAt)
  if (Number.isNaN(d.getTime())) return savedAt
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function openPlan(id: string) {
  detailModal?.destroy()
  detailPlanId = id
  const title = getPlan(id)?.name || '方案详情'
  detailModal = modal.create({
    preset: 'card',
    title,
    bordered: false,
    autoFocus: false,
    style: {width: 'min(420px, calc(100vw - 32px))'},
    segmented: {content: true},
    content: () =>
        h(
            'div',
            {
              class: 'plan-detail-scroll fa-scrollbar-hidden',
              style: {
                maxHeight: 'min(70vh, 640px)',
                overflowY: 'auto',
              },
            },
            [h(PlanDetail, {planId: id})],
        ),
    onAfterLeave: () => {
      if (detailPlanId === id) {
        detailPlanId = null
        detailModal = null
      }
    },
  })
}

function openRename(plan: SavedBetPlan) {
  if (!requireLogin()) return
  const draft = ref(plan.name)
  modal.create({
    preset: 'dialog',
    title: '修改方案名称',
    autoFocus: false,
    positiveText: '保存',
    negativeText: '取消',
    // defaultValue keeps NInput self-updating; draft only feeds onPositiveClick
    // so we do not depend on modal content re-rendering each keystroke.
    content: () =>
        h(NInput, {
          defaultValue: plan.name,
          maxlength: 40,
          showCount: true,
          placeholder: '方案名称',
          'onUpdate:value': (value: string) => {
            draft.value = value
          },
        }),
    onPositiveClick: async () => {
      if (!requireLogin()) return false
      if (!(await renamePlan(plan.id, draft.value))) {
        message.warning('名称不能为空或保存失败')
        return false
      }
      message.success('已改名')
      return true
    },
  })
}

async function confirmDelete(plan: SavedBetPlan) {
  if (!requireLogin()) return
  try {
    await removePlan(plan.id)
  } catch {
    message.error('删除失败，请稍后重试')
    return
  }
  if (detailPlanId === plan.id) {
    detailModal?.destroy()
    detailModal = null
    detailPlanId = null
  }
  message.success('已删除')
}

onMounted(() => {
  if (!requireLogin()) {
    // Login modal is open; list stays empty until they sign in and re-enter.
    return
  }
  void ensureLoaded()
})
</script>

<template>
  <div class="plans-panel">
    <!-- 手机：统计/日期做成卡片头，与列表合成一个整块；PC 这两项在顶栏第二行 -->
    <n-card
        class="plans-card"
        :class="{ 'plans-card--mobile': isPhone }"
        :bordered="false"
        content-style="padding: 0; flex: 1; min-height: 0; display: flex; flex-direction: column;"
    >
      <template v-if="isPhone" #header>
        <span class="plans-card-title">{{ dayPlanCountLabel }}</span>
      </template>
      <template v-if="isPhone" #header-extra>
        <FavoriteDatesPicker
            v-model="filterDate"
            :marked-days="planDays"
            legend="当天有方案（赛程日）"
        />
      </template>
      <n-scrollbar class="plans-scroll" trigger="hover">
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
                <span class="plan-saved-at">{{ formatPlanSavedAt(plan.savedAt) }}</span>
                <n-flex :size="8" align="center" @click.stop>
                  <n-button size="tiny" tertiary @click="openRename(plan)">
                    编辑
                  </n-button>
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
      </n-scrollbar>
    </n-card>
  </div>
</template>

<style scoped>
/* 面板填满 mine-outlet 的槽位，滚动条只在列表区出现 */
.plans-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding: 0 var(--fa-content-inline);
  box-sizing: border-box;
}

/* PC：卡片透明无边框，等同裸列表（统计/日期在顶栏第二行） */
.plans-card {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: transparent;
}

/* 手机：统计/日期 + 列表合成一个抬升卡片，与顶部标题分层 */
.plans-card--mobile {
  margin: 12px 0;
  background: var(--fa-bg-elevated);
  border-radius: 12px;
  overflow: hidden;
}

.plans-card--mobile :deep(.n-card-header) {
  flex-shrink: 0;
  padding: 12px 14px;
  border-bottom: 1px solid var(--fa-border);
}

.plans-card-title {
  font-size: 13px;
  color: var(--fa-text-secondary);
  white-space: nowrap;
}

:deep(.n-list.n-list--hoverable .n-list-item) {
  padding: 12px 0;
}

/* 手机：行内容对齐卡片头的左右留白，不贴卡片边 */
.plans-card--mobile :deep(.n-list.n-list--hoverable .n-list-item) {
  padding-inline: 14px;
}

.plans-scroll {
  flex: 1;
  min-height: 0;
}

.plans-empty {
  padding: 48px 0;
}

.plans-panel :deep(.n-thing .n-thing-header) {
  margin-bottom: 0;
}

.plans-panel :deep(.n-thing .n-thing-header .n-thing-header__title) {
  font-size: 14px;
}

.plan-saved-at {
  flex-shrink: 0;
  color: var(--fa-text-muted);
  font-size: 12px;
  font-weight: 400;
  white-space: nowrap;
}
</style>
