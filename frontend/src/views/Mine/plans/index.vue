<script setup lang="ts">
import {computed, h, onMounted, ref, watch} from 'vue'
import {NInput, useMessage, useModal, type ModalReactive} from 'naive-ui'
import {ChevronForwardOutline} from '@vicons/ionicons5'

import {fetchFixtureScores} from '@/api/fixtures'
import PlanDetail from '@/views/Mine/plans/PlanDetail.vue'
import {useAuthSession} from '@/composables/useAuthSession'
import {useBetPlans} from '@/composables/useBetPlans'
import {useHandicapRuleset} from '@/composables/useHandicapRuleset'
import {useIsPhone} from '@/composables/useMediaQuery'
import {selectedFixtureIds} from '@/utils/betCalculator'
import {
  planStatusLabel,
  planStatusTagType,
  settleBetPlan,
  summarizePlanStatuses,
  type FixtureScoreSnap,
  type PlanSettlement,
  type PlanWinCounts,
} from '@/utils/betPlanSettle'
import {ACCURACY_COLOR_BY_HIT_KEY} from '@/utils/accuracyColors'
import {formatScheduleDay, formatTime} from '@/utils/format'
import type {SavedBetPlan} from '@/utils/betPlans'
import FavoriteDatesPicker from '@/views/Favorites/components/FavoriteDatesPicker.vue'

defineOptions({name: 'BetPlans'})

const SCORE_CHUNK = 200

/** Same palette order as 赛程「历史统计」第一行：胜平负 / 每日推荐 / 比分. */
const PLAN_STAT_ITEMS = [
  {key: 'won' as const, label: '中奖', color: ACCURACY_COLOR_BY_HIT_KEY.result},
  {key: 'settled' as const, label: '已结算', color: ACCURACY_COLOR_BY_HIT_KEY.auto_pick},
  {key: 'total' as const, label: '全部', color: ACCURACY_COLOR_BY_HIT_KEY.score},
]

const message = useMessage()
const modal = useModal()
const mutatingPlanIds = new Set<string>()
const isPhone = useIsPhone()
const {requireLogin} = useAuthSession()
const {ruleset} = useHandicapRuleset()
const {
  plans,
  filterDate,
  plansForDay,
  ensureLoaded,
  renamePlan,
  removePlan,
  getPlan,
  planDays,
} = useBetPlans()

const dayPlans = computed(() => plansForDay(filterDate.value))
const scores = ref<Map<number, FixtureScoreSnap>>(new Map())
const scoresLoading = ref(false)

function settlementFor(plan: SavedBetPlan): PlanSettlement {
  return settleBetPlan(
      plan.selections,
      plan.fold,
      plan.multiplier,
      scores.value,
      ruleset.value,
  )
}

function statusFor(plan: SavedBetPlan): PlanSettlement['status'] {
  return settlementFor(plan).status
}

function countsFor(list: SavedBetPlan[]): PlanWinCounts {
  return summarizePlanStatuses(list.map(statusFor))
}

const dayStats = computed(() => countsFor(dayPlans.value))
const historyStats = computed(() => countsFor(plans.value))
const dayStatusById = computed(() => {
  const map = new Map<string, PlanSettlement['status']>()
  for (const plan of dayPlans.value) {
    map.set(plan.id, statusFor(plan))
  }
  return map
})

let detailModal: ModalReactive | null = null
let detailPlanId: string | null = null

async function loadScores() {
  const ids = [
    ...new Set(plans.value.flatMap((plan) => selectedFixtureIds(plan.selections))),
  ]
  if (!ids.length) {
    scores.value = new Map()
    return
  }
  scoresLoading.value = true
  try {
    const map = new Map<number, FixtureScoreSnap>()
    for (let i = 0; i < ids.length; i += SCORE_CHUNK) {
      const data = await fetchFixtureScores(ids.slice(i, i + SCORE_CHUNK))
      for (const row of data.fixtures) {
        map.set(row.fixture_id, row)
      }
    }
    scores.value = map
  } catch (err) {
    message.error(err instanceof Error ? err.message : '加载方案赛果失败')
  } finally {
    scoresLoading.value = false
  }
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
  if (mutatingPlanIds.has(plan.id)) return
  const draft = ref(plan.name)
  modal.create({
    preset: 'dialog',
    title: '修改方案名称',
    autoFocus: false,
    positiveText: '保存',
    negativeText: '取消',
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
      if (mutatingPlanIds.has(plan.id)) return false
      if (!requireLogin()) return false
      mutatingPlanIds.add(plan.id)
      try {
        if (!(await renamePlan(plan.id, draft.value))) {
          message.warning('名称不能为空或保存失败')
          return false
        }
        message.success('已改名')
        return true
      } finally {
        mutatingPlanIds.delete(plan.id)
      }
    },
  })
}

async function confirmDelete(plan: SavedBetPlan) {
  if (mutatingPlanIds.has(plan.id)) return
  if (!requireLogin()) return
  mutatingPlanIds.add(plan.id)
  try {
    await removePlan(plan.id)
  } catch {
    message.error('删除失败，请稍后重试')
    return
  } finally {
    mutatingPlanIds.delete(plan.id)
  }
  if (detailPlanId === plan.id) {
    detailModal?.destroy()
    detailModal = null
    detailPlanId = null
  }
  message.success('已删除')
}

watch(
    () => plans.value.map((p) => p.id).join(','),
    () => {
      if (plans.value.length) void loadScores()
      else scores.value = new Map()
    },
)

onMounted(() => {
  if (!requireLogin()) {
    return
  }
  void ensureLoaded().then(() => loadScores())
})
</script>

<template>
  <div class="plans-panel">
    <n-grid
        class="plans-stats"
        :cols="isPhone ? 1 : 2"
        :x-gap="10"
        :y-gap="10"
    >
      <n-gi>
        <n-card
            size="small"
            :bordered="false"
            class="plans-stat-card"
            :segmented="{ content: true }"
        >
          <template #header>
            <span class="plans-stat-title">当日统计</span>
          </template>
          <template #header-extra>
            <n-text depth="3" style="font-size: 12px;">{{ formatScheduleDay(filterDate) }}</n-text>
          </template>
          <n-spin :show="scoresLoading">
            <n-grid :cols="3" :x-gap="8" class="plans-stat-grid">
              <n-gi v-for="item in PLAN_STAT_ITEMS" :key="item.key">
                <n-statistic :label="item.label" tabular-nums>
                  <span :style="{ color: item.color }">{{ dayStats[item.key] }}</span>
                </n-statistic>
              </n-gi>
            </n-grid>
          </n-spin>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card
            size="small"
            :bordered="false"
            class="plans-stat-card"
            :segmented="{ content: true }"
        >
          <template #header>
            <span class="plans-stat-title">历史统计</span>
          </template>
          <template #header-extra>
            <n-text depth="3" style="font-size: 12px;">全部已存方案</n-text>
          </template>
          <n-spin :show="scoresLoading">
            <n-grid :cols="3" :x-gap="8" class="plans-stat-grid">
              <n-gi v-for="item in PLAN_STAT_ITEMS" :key="item.key">
                <n-statistic :label="item.label" tabular-nums>
                  <span :style="{ color: item.color }">{{ historyStats[item.key] }}</span>
                </n-statistic>
              </n-gi>
            </n-grid>
          </n-spin>
        </n-card>
      </n-gi>
    </n-grid>
    <div class="plans-gap">
      <n-card
          class="plans-card"
          :class="{ 'plans-card--mobile': isPhone }"
          :bordered="false"
          content-style="padding:0; flex: 1; min-height: 0; display: flex; flex-direction: column;"
      >
        <template v-if="isPhone" #header>
          <span class="plans-card-title">方案列表</span>
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
              <n-thing>
                <template #header>
                  <n-flex :size="8" align="center" class="plan-title-row">
                    <n-ellipsis class="plan-name">{{ plan.name }}</n-ellipsis>
                    <n-tag
                        size="small"
                        :bordered="false"
                        :type="planStatusTagType(dayStatusById.get(plan.id) ?? 'pending')"
                        :class="{ 'fa-tag-missed': (dayStatusById.get(plan.id) ?? 'pending') === 'lost' }"
                    >
                      {{ planStatusLabel(dayStatusById.get(plan.id) ?? 'pending') }}
                    </n-tag>
                  </n-flex>
                </template>
                <template #header-extra>
                  <n-flex :size="10" align="center">
                    <span class="plan-saved-at">{{ formatTime(plan.savedAt) }}</span>
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
  </div>
</template>

<style scoped>
.plans-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  box-sizing: border-box;
  gap: 10px;
  /* 手机端本页隐藏底栏导航，底部留白与安全区只能由本页承担。 */
  padding: 10px 0 calc(var(--fa-content-block-end) + env(safe-area-inset-bottom, 0px));
}

.plans-stats {
  flex-shrink: 0;
  padding: 0 12px;
}

.plans-stat-card {
  background: var(--fa-bg-elevated);
  height: 100%;
}

.plans-stat-title {
  font-size: 14px;
  font-weight: 600;
}

.plans-stat-grid :deep(.n-grid-item) {
  min-width: 0;
}

.plans-stat-card :deep(.n-statistic-value__content) {
  font-size: 20px;
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
}

.plans-gap {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  padding: 0 12px;
  overflow: hidden;
}

.plans-card {
  display: flex;
  flex-direction: column;
  flex: 1;
  width: 100%;
  min-height: 0;
  background: transparent;
}

.plans-card--mobile {
  margin: 0;
  background: var(--fa-bg-elevated);
  overflow: hidden;
}

.plans-card--mobile :deep(.n-card-content) {
  padding: 0;
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
  padding: 12px;
}

.plans-card--mobile :deep(.n-list.n-list--hoverable .n-list-item) {
  padding-inline: 14px;
}

.plans-scroll {
  flex: 1;
  min-height: 0;
}

/* 末条方案不要贴住卡片内下边缘。 */
.plans-scroll :deep(.n-scrollbar-content) {
  padding-bottom: 8px;
}

.plans-empty {
  padding: 48px 0;
}

.plans-panel :deep(.n-thing .n-thing-header) {
  margin-bottom: 0;
}

.plans-panel :deep(.n-thing .n-thing-header .n-thing-header__title) {
  min-width: 0;
  font-size: 14px;
}

.plan-title-row {
  min-width: 0;
}

.plan-title-row :deep(.n-tag) {
  flex-shrink: 0;
}

.plan-name {
  min-width: 0;
  font-size: 14px;
  font-weight: 500;
}

.plan-saved-at {
  flex-shrink: 0;
  color: var(--fa-text-muted);
  font-size: 12px;
  font-weight: 400;
  white-space: nowrap;
}

@media (max-width: 767px) {
  .plans-panel {
    padding-top: 12px;
  }
}
</style>
