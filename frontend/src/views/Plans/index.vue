<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { ChevronForwardOutline } from '@vicons/ionicons5'

import PlanDetail from '@/views/Plans/PlanDetail.vue'
import { useBetPlans } from '@/composables/useBetPlans'
import { formatScheduleDay, parseApiDate } from '@/utils/format'
import type { SavedBetPlan } from '@/utils/betPlans'

defineOptions({ name: 'BetPlans' })

const message = useMessage()
const {
  filterDate,
  plansForDay,
  ensureLoaded,
  renamePlan,
  removePlan,
  getPlan,
} = useBetPlans()

const editingPlan = ref<SavedBetPlan | null>(null)
const renameDraft = ref('')
const showRename = ref(false)
const detailPlanId = ref<string | null>(null)
const showDetail = ref(false)

const dayPlans = computed(() => plansForDay(filterDate.value))
const detailTitle = computed(
  () => (detailPlanId.value && getPlan(detailPlanId.value)?.name) || '方案详情',
)

/** yyyy-MM-dd HH:mm in local timezone. */
function formatPlanSavedAt(savedAt: string): string {
  const d = parseApiDate(savedAt)
  if (Number.isNaN(d.getTime())) return savedAt
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function openPlan(id: string) {
  detailPlanId.value = id
  showDetail.value = true
}

function closeDetail() {
  showDetail.value = false
  detailPlanId.value = null
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
  if (detailPlanId.value === plan.id) closeDetail()
  message.success('已删除')
}

onMounted(() => {
  void ensureLoaded()
})
</script>

<template>
  <div class="plans-panel">
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
      </div>
    </n-scrollbar>

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

    <n-modal
      v-model:show="showDetail"
      preset="card"
      :title="detailTitle"
      :bordered="false"
      :style="{ width: 'min(420px, calc(100vw - 32px))' }"
      :segmented="{ content: true }"
      display-directive="if"
      @after-leave="detailPlanId = null"
    >
      <div class="plan-detail-scroll fa-scrollbar-hidden">
        <PlanDetail :plan-id="detailPlanId" />
      </div>
    </n-modal>
  </div>
</template>

<style scoped>
.plan-detail-scroll {
  max-height: min(70vh, 640px);
  overflow-y: auto;
}

.plans-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--fa-bg);
}

.plans-scroll {
  flex: 1;
  min-height: 0;
}

.plans-scroll-pad {
  width: 100%;
  box-sizing: border-box;
  padding-top: 12px;
  padding-bottom: 24px;
}

.plans-empty {
  padding: 48px 0;
}

.plans-panel :deep(.n-thing-header) {
  margin-bottom: 0;
}

.plan-saved-at {
  flex-shrink: 0;
  color: var(--fa-text-muted);
  font-size: 12px;
  font-weight: 400;
  white-space: nowrap;
}
</style>
