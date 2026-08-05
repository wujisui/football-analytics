<script setup lang="ts">
import { TrashOutline } from '@vicons/ionicons5'
import { useMessage } from 'naive-ui'
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import BetSelectionList from '@/views/Predictions/components/BetSelectionList.vue'
import { useBetCalculator } from '@/views/Predictions/composables/useBetCalculator'
import { useBetPlans } from '@/composables/useBetPlans'
import {
  foldModeLabel,
  outcomeTitle,
  STAKE_PER_BET,
  type CalcSelection,
} from '@/utils/betCalculator'
import { defaultPlanName } from '@/utils/betPlans'

const props = withDefaults(
  defineProps<{
    /** 仅底部摘要（手机计算器页：列表在外，摘要贴底） */
    footerOnly?: boolean
  }>(),
  { footerOnly: false },
)

const message = useMessage()
const router = useRouter()
const {
  matchCount,
  multiplier,
  fold,
  foldOptions,
  result,
  selections,
  groupedSelections,
  clearAll,
  removeFixture,
} = useBetCalculator()
const { savePlan } = useBetPlans()

const showDetails = ref(false)
const showFormula = ref(false)
const showSave = ref(false)
const saveName = ref('')

function openDetails() {
  if (!groupedSelections.value.length) return
  showDetails.value = true
}

function openFormula() {
  if (result.value.combos.length) showFormula.value = true
}

function openSave() {
  if (!matchCount.value) return
  saveName.value = defaultPlanName(selections.value, fold.value)
  showSave.value = true
}

async function confirmSave(): Promise<boolean> {
  if (!selections.value.length) return false
  const plan = await savePlan({
    name: saveName.value,
    fold: fold.value,
    multiplier: multiplier.value,
    selections: selections.value,
  })
  if (!plan) {
    message.error('保存失败，请稍后重试')
    return false
  }
  showSave.value = false
  message.success(`已保存「${plan.name}」`)
  return true
}

/** Save first — jumping away without persisting silently dropped the plan. */
async function saveAndGoPlans() {
  if (!(await confirmSave())) return
  void router.push({ name: 'bet-plans' })
}

function legLabel(pick: CalcSelection): string {
  return `${pick.homeName} vs ${pick.awayName} ${pick.playLabel}${outcomeTitle(pick.market, pick.outcome)}`
}

function oddsFormula(picks: CalcSelection[]): string {
  return picks.map((pick) => pick.odd).join(' × ')
}

watch(matchCount, (count) => {
  if (!count) showDetails.value = false
})

defineExpose({ openFormula, openDetails })
</script>

<template>
  <div class="bet-details-panel" :class="{ 'footer-only': props.footerOnly }">
    <div v-if="!props.footerOnly" class="scroll-fill">
      <n-scrollbar style="height: 100%;" trigger="hover">
        <BetSelectionList
          :groups="groupedSelections"
          empty-description="在「计算器」点选玩法后显示已选场次"
          @remove="removeFixture"
        />
      </n-scrollbar>
    </div>

    <n-flex vertical :size="8" class="details-footer">
      <n-grid :cols="12" :x-gap="8">
        <n-gi :span="5">
          <n-select
            v-model:value="fold"
            size="small"
            :options="foldOptions"
            :disabled="!foldOptions.length"
            placeholder="过关方式"
          />
        </n-gi>
        <n-gi :span="5">
          <n-input-number
            v-model:value="multiplier"
            size="small"
            :min="1"
            :max="99"
            button-placement="both"
          >
            <template #prefix>倍数</template>
          </n-input-number>
        </n-gi>
        <n-gi :span="2">
          <n-button
            block
            size="small"
            type="error"
            tertiary
            :disabled="!matchCount"
            aria-label="清空已选"
            @click="clearAll"
          >
            <template #icon>
              <n-icon :component="TrashOutline" />
            </template>
          </n-button>
        </n-gi>
      </n-grid>

      <n-flex :wrap="false" align="center" justify="space-between" :size="8">
        <n-text depth="3" style="flex: 1; min-width: 0;">
          已选 {{ matchCount }} 场 · {{ foldModeLabel(fold) }} ·
          {{ result.betCount }} 注 {{ result.stakeYuan }} 元 · 预计奖金
          <n-text type="error" strong>
            {{ result.estimatedPrize || '—' }}
          </n-text>
          元
        </n-text>
        <n-flex :size="6" :wrap="false">
          <n-button
            size="tiny"
            type="primary"
            secondary
            :disabled="!matchCount"
            @click="openSave"
          >
            保存方案
          </n-button>
          <n-button
            v-if="props.footerOnly"
            size="tiny"
            type="primary"
            :disabled="!groupedSelections.length"
            @click="openDetails"
          >
            投注详情
          </n-button>
        </n-flex>
      </n-flex>

      <n-text depth="3" style="text-align: center;">
        提示：计算器仅供赛前参考，不提供购彩服务
      </n-text>
    </n-flex>

    <n-modal
      v-model:show="showDetails"
      preset="card"
      title="投注详情"
      :bordered="false"
      to="body"
      :style="{
        width: '92%',
        maxWidth: '480px',
        maxHeight: 'calc(100vh - 32px)',
        margin: 'auto',
      }"
    >
      <div class="details-modal-body">
        <n-scrollbar style="height: 100%;" trigger="hover">
          <BetSelectionList
            :groups="groupedSelections"
            @remove="removeFixture"
          />
        </n-scrollbar>
      </div>
    </n-modal>

    <n-modal
      v-model:show="showFormula"
      preset="card"
      :title="`奖金算式 · ${foldModeLabel(fold)}`"
      :bordered="false"
      to="body"
      :style="{
        width: '20%',
        minWidth: '360px',
        maxWidth: 'calc(100vw - 32px)',
        maxHeight: 'calc(100vh - 32px)',
        margin: 'auto',
      }"
    >
      <div class="formula-modal-body">
        <div class="scroll-fill">
          <n-scrollbar style="height: 100%;" trigger="hover">
            <n-flex vertical :size="10" style="padding: 0 8px;">
              <n-card
                v-for="(combo, idx) in result.combos"
                :key="idx"
                size="small"
                :bordered="false"
                style="width: 100%; background: var(--fa-bg-soft);"
              >
                <n-flex vertical :size="4">
                  <n-text v-if="result.combos.length > 1" strong depth="2">
                    第 {{ idx + 1 }} 注
                  </n-text>
                  <n-flex v-if="result.combos.length > 1" vertical :size="2">
                    <n-text
                      v-for="pick in combo.picks"
                      :key="`${pick.fixtureId}-${pick.market}-${pick.outcome}`"
                      depth="3"
                    >
                      {{ legLabel(pick) }}
                    </n-text>
                  </n-flex>
                  <n-text depth="2">
                    {{ oddsFormula(combo.picks) }} =
                    <n-text strong>{{ combo.oddsProduct }}</n-text>
                  </n-text>
                  <n-text depth="2">
                    {{ combo.oddsProduct }} × {{ STAKE_PER_BET }} 元 ×
                    {{ multiplier }} 倍 =
                    <n-text type="error" strong>{{ combo.prize }}</n-text>
                    元
                  </n-text>
                </n-flex>
              </n-card>
            </n-flex>
          </n-scrollbar>
        </div>

        <n-flex
          align="baseline"
          :size="4"
          style="margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--fa-border);"
        >
          <n-text>预计奖金合计</n-text>
          <n-text type="error" strong>{{ result.estimatedPrize }}</n-text>
          <n-text>元（投注 {{ result.stakeYuan }} 元）</n-text>
        </n-flex>
      </div>
    </n-modal>
    <n-modal
      v-model:show="showSave"
      preset="dialog"
      title="保存方案"
      positive-text="保存"
      negative-text="取消"
      :positive-button-props="{ disabled: !matchCount }"
      @positive-click="() => confirmSave()"
    >
      <n-space vertical :size="10">
        <n-input
          v-model:value="saveName"
          maxlength="40"
          show-count
          placeholder="方案名称"
        />
        <n-text depth="3" style="font-size: 12px;">
          保存后可在「我的 → 我的方案」按赛程日回溯命中情况。
          <n-button
            text
            type="primary"
            size="tiny"
            :disabled="!matchCount"
            @click="saveAndGoPlans"
          >
            保存并查看
          </n-button>
        </n-text>
      </n-space>
    </n-modal>
  </div>
</template>

<style scoped>
.bet-details-panel {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.bet-details-panel.footer-only {
  display: block;
  height: auto;
  overflow: visible;
}

.scroll-fill {
  min-height: 0;
  overflow: hidden;
}

.details-footer {
  flex-shrink: 0;
  padding: 10px;
  border-top: 1px solid var(--fa-border);
  background-color: var(--fa-bg-elevated);
}

.footer-only .details-footer {
  border-top: none;
  padding-bottom: max(10px, env(safe-area-inset-bottom, 0px));
}

.details-modal-body {
  height: min(70vh, 640px);
  min-height: 0;
  overflow: hidden;
}

.formula-modal-body {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  height: min(70vh, 640px);
  min-height: 0;
}
</style>
