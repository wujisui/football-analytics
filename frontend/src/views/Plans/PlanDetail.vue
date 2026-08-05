<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { ChevronBackOutline } from '@vicons/ionicons5'

import { fetchFixtureScores } from '@/api/fixtures'
import { useBetPlans } from '@/composables/useBetPlans'
import {
  foldModeLabel,
  outcomeTitle,
  selectedFixtureIds,
  type CalcSelection,
} from '@/utils/betCalculator'
import {
  planStatusLabel,
  settleBetPlan,
  type FixtureScoreSnap,
  type LegVerdict,
  type PlanSettlement,
} from '@/utils/betPlanSettle'

defineOptions({ name: 'BetPlanDetail' })

const props = defineProps<{
  planId: string
}>()

const route = useRoute()
const router = useRouter()
const message = useMessage()
const { getPlan, reload } = useBetPlans()

const plan = computed(() => getPlan(props.planId || String(route.params.planId)))
const loadingScores = ref(false)
const scores = ref<Map<number, FixtureScoreSnap>>(new Map())

const settlement = computed((): PlanSettlement | null => {
  const p = plan.value
  if (!p) return null
  return settleBetPlan(p.selections, p.fold, p.multiplier, scores.value)
})

function verdictLabel(v: LegVerdict): string {
  if (v === 'hit') return '中'
  if (v === 'miss') return '未中'
  if (v === 'void') return '走水'
  return '待定'
}

function verdictType(v: LegVerdict): 'success' | 'error' | 'warning' | 'default' {
  if (v === 'hit') return 'success'
  if (v === 'miss') return 'error'
  if (v === 'void') return 'warning'
  return 'default'
}

function pickLine(pick: CalcSelection): string {
  return `${pick.homeName} vs ${pick.awayName} · ${pick.playLabel}${outcomeTitle(pick.market, pick.outcome)} @${pick.odd}`
}

async function loadScores() {
  const p = plan.value
  if (!p) return
  const ids = selectedFixtureIds(p.selections)
  if (!ids.length) return
  loadingScores.value = true
  try {
    const data = await fetchFixtureScores(ids)
    const map = new Map<number, FixtureScoreSnap>()
    for (const row of data.fixtures) {
      map.set(row.fixture_id, row)
    }
    scores.value = map
  } catch (err) {
    message.error(err instanceof Error ? err.message : '加载赛果失败')
  } finally {
    loadingScores.value = false
  }
}

function goBack() {
  void router.push({ name: 'bet-plans' })
}

onMounted(() => {
  void reload().then(() => {
    void loadScores()
  })
})
</script>

<template>
  <div class="fa-page-frame">
    <div class="fa-page-shell plan-detail-shell">
      <div class="plan-detail-header fa-page-toolbar">
        <div class="plan-detail-toolbar">
          <n-button size="small" quaternary aria-label="返回" @click="goBack">
            <template #icon>
              <n-icon :component="ChevronBackOutline" />
            </template>
          </n-button>
          <span class="plan-detail-title">{{ plan?.name || '方案详情' }}</span>
          <span aria-hidden="true" class="plan-detail-toolbar-spacer"></span>
        </div>
      </div>

      <n-scrollbar class="plan-detail-scroll" trigger="hover">
        <div class="fa-page-content-padding plan-detail-pad">
          <n-empty v-if="!plan" description="方案不存在或已删除" />

          <n-spin v-else :show="loadingScores">
            <n-space vertical :size="12">
              <n-card size="small" :bordered="false">
                <n-descriptions label-placement="left" :column="1" size="small">
                  <n-descriptions-item label="过关">
                    {{ foldModeLabel(plan.fold) }} · {{ plan.multiplier }} 倍
                  </n-descriptions-item>
                  <n-descriptions-item label="场次">
                    {{ selectedFixtureIds(plan.selections).length }} 场
                  </n-descriptions-item>
                  <n-descriptions-item label="状态">
                    <n-tag
                      size="small"
                      :type="
                        settlement?.status === 'won'
                          ? 'success'
                          : settlement?.status === 'lost'
                            ? 'error'
                            : settlement?.status === 'void'
                              ? 'warning'
                              : 'default'
                      "
                      :bordered="false"
                    >
                      {{ settlement ? planStatusLabel(settlement.status) : '—' }}
                    </n-tag>
                  </n-descriptions-item>
                  <n-descriptions-item label="投入">
                    {{ settlement?.stakeYuan ?? '—' }} 元
                  </n-descriptions-item>
                  <n-descriptions-item label="预计奖金">
                    {{ settlement?.estimatedPrize ?? '—' }} 元
                  </n-descriptions-item>
                  <n-descriptions-item label="实际奖金">
                    <n-text
                      :type="settlement?.status === 'won' ? 'error' : undefined"
                      strong
                    >
                      {{settlement?.status === 'pending' ? '待结算' : `${settlement?.actualPrize ?? 0} 元`}}
                    </n-text>
                  </n-descriptions-item>
                </n-descriptions>
                <n-text depth="3" style="font-size: 12px; display: block; margin-top: 8px;">
                  走水场次作废（赔率按 1 计），用剩余场次结算；取消/延期场次同样作废。
                </n-text>
              </n-card>

              <n-card size="small" title="各场选项" :bordered="false">
                <n-list>
                  <n-list-item v-for="(leg, idx) in settlement?.legs || []" :key="idx">
                    <n-thing :title="pickLine(leg.pick)">
                      <template #description>
                        <n-text depth="3">
                          {{ leg.pick.kickoff }}
                          <template v-if="leg.scoreText"> · 比分 {{ leg.scoreText }}</template>
                        </n-text>
                      </template>
                      <template #header-extra>
                        <n-tag size="small" :type="verdictType(leg.verdict)" :bordered="false">
                          {{ verdictLabel(leg.verdict) }}
                        </n-tag>
                      </template>
                    </n-thing>
                  </n-list-item>
                </n-list>
              </n-card>
            </n-space>
          </n-spin>
        </div>
      </n-scrollbar>
    </div>
  </div>
</template>

<style scoped>
.plan-detail-shell {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--fa-bg);
}

.plan-detail-header {
  flex-shrink: 0;
  width: 100%;
  max-width: var(--fa-mine-page-max-width);
  margin: 0 auto;
  box-sizing: border-box;
}

.plan-detail-toolbar {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) 34px;
  align-items: center;
  width: 100%;
}

.plan-detail-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--fa-text-strong);
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plan-detail-toolbar-spacer {
  width: 34px;
}

.plan-detail-scroll {
  flex: 1;
  min-height: 0;
}

.plan-detail-pad {
  max-width: var(--fa-mine-page-max-width);
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
  padding-top: 12px;
  padding-bottom: 24px;
}
</style>
