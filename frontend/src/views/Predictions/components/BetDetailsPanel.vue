<script setup lang="ts">
import { TrashOutline } from '@vicons/ionicons5'
import { ref } from 'vue'

import { useBetCalculator } from '@/views/Predictions/composables/useBetCalculator'
import {
  foldModeLabel,
  outcomeTitle,
  STAKE_PER_BET,
  type CalcSelection,
} from '@/utils/betCalculator'
import { leagueTagColor } from '@/utils/format'

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
    <div v-if="!props.footerOnly" class="scroll-fill">
      <n-scrollbar style="height: 100%;" trigger="hover">
        <n-flex vertical :size="10" style="padding: 10px;">
          <n-empty
            v-if="!groupedSelections.length"
            description="在「计算器」点选玩法后显示已选场次"
            size="small"
          />

          <n-card
            v-for="group in groupedSelections"
            v-else
            :key="group.fixtureId"
            size="small"
            :bordered="false"
            header-style="font-size: inherit; font-weight: 400;"
            style="background: var(--fa-bg-soft);"
          >
            <template #header>
              <n-flex :wrap="false" align="center" :size="8" style="min-width: 0;">
                <n-ellipsis style="flex: 0 1 auto; min-width: 0;">
                  <n-text :style="{ color: leagueTagColor(group.leagueId) }">
                    {{ group.leagueName }}
                  </n-text>
                </n-ellipsis>
                <n-text depth="3" style="flex-shrink: 0; font-size: 12px;">
                  {{ group.kickoff }}
                </n-text>
              </n-flex>
            </template>
            <template #header-extra>
              <n-button
                size="tiny"
                type="error"
                quaternary
                circle
                aria-label="移除场次"
                @click="removeFixture(group.fixtureId)"
              >
                <template #icon>
                  <n-icon :component="TrashOutline" />
                </template>
              </n-button>
            </template>

            <n-flex vertical :size="8">
              <n-flex
                :wrap="false"
                justify="center"
                align="center"
                :size="6"
                class="matchup"
              >
                <n-ellipsis>{{ group.homeName }}</n-ellipsis>
                <n-text depth="3" class="versus">VS</n-text>
                <n-ellipsis>{{ group.awayName }}</n-ellipsis>
              </n-flex>
              <n-flex
                v-for="pick in group.picks"
                :key="`${pick.market}-${pick.outcome}`"
                :wrap="false"
                align="center"
                :size="8"
              >
                <n-tag size="small" :bordered="false">{{ pick.playLabel }}</n-tag>
                <n-tag size="small" :bordered="false" type="warning">
                  {{ pick.pickLabel }}
                </n-tag>
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
        <n-text depth="3" style="flex: 1; min-width: 0;">
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

      <n-text depth="3" style="text-align: center;">
        提示：计算器仅供赛前参考，不提供购彩服务
      </n-text>
    </n-flex>

    <n-modal
      v-model:show="showFormula"
      preset="card"
      :title="`奖金算式 · ${foldModeLabel(fold)}`"
      :bordered="false"
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
  </div>
</template>

<style scoped>
/* 仅保留 Naive 无法用 props 表达的壳层布局：填满高度、滚动区、底栏固定 */
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

/* header 内 n-ellipsis 需要父级可收缩，Naive 默认未给 __main 设 min-width */
.bet-details-panel :deep(.n-card-header__main) {
  min-width: 0;
}

.matchup {
  width: 100%;
  min-width: 0;
}

.matchup :deep(.n-ellipsis) {
  flex: 0 1 auto;
  min-width: 0;
  font-weight: 600;
}

.versus {
  flex: 0 0 auto;
  white-space: nowrap;
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

.formula-modal-body {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  height: min(70vh, 640px);
  min-height: 0;
}
</style>
