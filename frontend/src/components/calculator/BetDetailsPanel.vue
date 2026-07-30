<script setup lang="ts">
import { ref } from 'vue'

import { useBetCalculator } from '@/composables/useBetCalculator'
import {
  foldModeLabel,
  outcomeTitle,
  STAKE_PER_BET,
  type CalcSelection,
} from '@/utils/betCalculator'

const props = withDefaults(
  defineProps<{
    /** 仅底部摘要（手机计算器页：列表在外，摘要贴底） */
    footerOnly?: boolean
  }>(),
  { footerOnly: false },
)

const {
  matchCount,
  multiplier,
  fold,
  foldOptions,
  result,
  groupedSelections,
  clearAll,
  removeFixture,
} = useBetCalculator()

const showFormula = ref(false)

function openFormula() {
  if (result.value.combos.length) showFormula.value = true
}

function legLabel(pick: CalcSelection): string {
  return `${pick.homeName} vs ${pick.awayName} ${pick.playLabel}${outcomeTitle(pick.market, pick.outcome)}`
}

function oddsFormula(picks: CalcSelection[]): string {
  return picks.map((pick) => pick.odd).join(' × ')
}

defineExpose({ openFormula })
</script>

<template>
  <div class="bet-details-panel" :class="{ 'footer-only': props.footerOnly }">
    <div v-if="!props.footerOnly" class="selection-scroll-shell">
      <n-scrollbar style="height: 100%;" trigger="hover">
        <n-flex vertical :size="10" class="selection-list">
          <n-empty
            v-if="!groupedSelections.length"
            description="在中间「计算器」点选玩法后显示已选场次"
            size="small"
            class="empty"
          />

          <n-card
            v-for="group in groupedSelections"
            v-else
            :key="group.fixtureId"
            size="small"
            :bordered="false"
            class="selection-card"
          >
            <n-flex vertical :size="6">
              <n-flex :wrap="false" align="center" :size="8">
                <n-ellipsis class="selection-league">
                  <n-text depth="3">{{ group.leagueName }}</n-text>
                </n-ellipsis>
                <n-text depth="3" class="selection-kickoff">
                  {{ group.kickoff }}
                </n-text>
                <n-button
                  text
                  size="tiny"
                  type="error"
                  @click="removeFixture(group.fixtureId)"
                >
                  移除
                </n-button>
              </n-flex>

              <n-text strong>
                {{ group.homeName }} VS {{ group.awayName }}
              </n-text>

              <n-flex
                v-for="pick in group.picks"
                :key="`${pick.market}-${pick.outcome}`"
                justify="space-between"
                align="center"
                :wrap="false"
                class="selection-pick"
              >
                <n-text depth="2">{{ pick.playLabel }}</n-text>
                <n-text type="warning" strong>{{ pick.pickLabel }}</n-text>
              </n-flex>
            </n-flex>
          </n-card>
        </n-flex>
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
            quaternary
            :disabled="!matchCount"
            @click="clearAll"
          >
            清空
          </n-button>
        </n-gi>
      </n-grid>

      <n-flex :wrap="false" align="center" justify="space-between" :size="8">
        <n-text depth="3" class="bet-summary">
          已选 {{ matchCount }} 场 · {{ foldModeLabel(fold) }} ·
          {{ result.betCount }} 注 {{ result.stakeYuan }} 元 · 预计奖金
          <n-text type="error" strong>
            {{ result.estimatedPrize || '—' }}
          </n-text>
          元
        </n-text>
        <n-button
          v-if="props.footerOnly"
          size="tiny"
          secondary
          :disabled="!result.combos.length"
          @click="openFormula"
        >
          奖金算式
        </n-button>
      </n-flex>

      <n-text depth="3" class="disclaimer">
        提示：计算器仅供赛前参考，不提供购彩服务
      </n-text>
    </n-flex>

    <n-modal
      v-model:show="showFormula"
      preset="card"
      :title="`奖金算式 · ${foldModeLabel(fold)}`"
      :bordered="false"
      class="formula-modal"
      :style="{
        width: '20%',
        minWidth: '360px',
        maxWidth: 'calc(100vw - 32px)',
        maxHeight: 'calc(100vh - 32px)',
        margin: 'auto',
      }"
    >
      <div class="formula-modal-body">
        <div class="formula-scroll">
          <n-scrollbar style="height: 100%;" trigger="hover">
            <n-flex vertical align="center" :size="10" class="formula-list">
              <n-card
                v-for="(combo, idx) in result.combos"
                :key="idx"
                size="small"
                :bordered="false"
                class="formula-card"
              >
                <n-flex vertical :size="4">
                  <n-text
                    v-if="result.combos.length > 1"
                    strong
                    depth="2"
                  >
                    第 {{ idx + 1 }} 注
                  </n-text>

                  <n-flex
                    v-if="result.combos.length > 1"
                    vertical
                    :size="2"
                  >
                    <n-text
                      v-for="pick in combo.picks"
                      :key="`${pick.fixtureId}-${pick.market}-${pick.outcome}`"
                      depth="3"
                      class="formula-leg"
                    >
                      {{ legLabel(pick) }}
                    </n-text>
                  </n-flex>

                  <n-text depth="2" class="formula-line">
                    {{ oddsFormula(combo.picks) }} =
                    <n-text strong>{{ combo.oddsProduct }}</n-text>
                  </n-text>
                  <n-text depth="2" class="formula-line">
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

        <n-flex align="baseline" :size="4" class="formula-total">
          <n-text>预计奖金合计</n-text>
          <n-text type="error" strong>{{ result.estimatedPrize }}</n-text>
          <n-text>元（投注 {{ result.stakeYuan }} 元）</n-text>
        </n-flex>
      </div>
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

.selection-scroll-shell,
.formula-scroll {
  min-height: 0;
  overflow: hidden;
}

.selection-list {
  padding: 10px;
}

.empty {
  padding: 24px 8px;
}

.selection-card {
  background: var(--fa-bg-soft);
}

.selection-card :deep(.n-card-content) {
  padding: 10px;
}

.selection-league {
  flex: 1;
  min-width: 0;
}

.selection-kickoff {
  flex-shrink: 0;
  font-size: 12px;
}

.selection-pick {
  padding: 6px 8px;
  border-radius: 4px;
  background: var(--fa-bg-elevated);
  font-size: 12px;
}

.details-footer {
  flex-shrink: 0;
  padding: 10px;
  border-top: 1px solid var(--fa-border);
  background: var(--fa-bg-elevated);
}

.footer-only .details-footer {
  border-top: none;
  padding-bottom: max(10px, env(safe-area-inset-bottom, 0px));
}

.bet-summary {
  flex: 1;
  min-width: 0;
  font-size: 12px;
}

.disclaimer {
  text-align: center;
  font-size: 11px;
}

.formula-modal {
  align-self: center;
  overflow: hidden;
}

.formula-modal-body {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  height: min(70vh, 640px);
  min-height: 0;
}

.formula-list {
  padding: 0 8px;
}

.formula-card {
  width: 100%;
  background: var(--fa-bg-soft);
  box-sizing: border-box;
}

.formula-card :deep(.n-card-content) {
  padding: 8px;
}

.formula-leg {
  font-size: 11px;
}

.formula-line {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  word-break: break-word;
}

.formula-total {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--fa-border);
  font-size: 13px;
  text-align: left;
}
</style>
