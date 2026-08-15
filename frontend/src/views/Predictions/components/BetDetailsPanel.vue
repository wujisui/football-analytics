<script setup lang="ts">
import { ImageOutline, TrashOutline } from '@vicons/ionicons5'
import { useMessage } from 'naive-ui'
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import BetSelectionList from '@/views/Predictions/components/BetSelectionList.vue'
import { useBetCalculator } from '@/views/Predictions/composables/useBetCalculator'
import { useAuthSession } from '@/composables/useAuthSession'
import { useBetPlans } from '@/composables/useBetPlans'
import { useIsPhone } from '@/composables/useMediaQuery'
import {
  foldModeLabel,
  outcomeTitle,
  STAKE_PER_BET,
  type CalcSelection,
} from '@/utils/betCalculator'
import { defaultPlanName } from '@/utils/betPlans'
import { saveDomAsPng, sharePngFile } from '@/utils/saveDomImage'
import { todayDate } from '@/utils/homeDateStrip'

const props = withDefaults(
  defineProps<{
    /** 仅底部摘要（手机计算器页：列表在外，摘要贴底） */
    footerOnly?: boolean
  }>(),
  { footerOnly: false },
)

const message = useMessage()
const router = useRouter()
const isPhone = useIsPhone()
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
const { requireLogin } = useAuthSession()

const showDetails = ref(false)
const showFormula = ref(false)
const showSave = ref(false)
const saveName = ref('')
const savingImage = ref(false)
const detailsExportRef = ref<HTMLElement | null>(null)
const previewUrl = ref<string | null>(null)
const previewFile = ref<File | null>(null)
const sharingPreview = ref(false)

const detailsModalStyle = computed(() =>
  isPhone.value
    ? {
        width: 'min(400px, calc(100vw - 40px))',
        maxHeight: 'min(68vh, 560px)',
        margin: '12vh auto auto',
      }
    : {
        width: '92%',
        maxWidth: '480px',
        maxHeight: 'calc(100vh - 32px)',
        margin: 'auto',
      },
)

function openDetails() {
  if (!groupedSelections.value.length) return
  showDetails.value = true
}

function openFormula() {
  if (result.value.combos.length) showFormula.value = true
}

function openSave() {
  if (!matchCount.value) return
  if (!requireLogin()) return
  saveName.value = defaultPlanName(selections.value, fold.value)
  showSave.value = true
}

async function confirmSave(): Promise<boolean> {
  if (!requireLogin()) return false
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
  void router.push({ name: 'mine-plans' })
}

function legLabel(pick: CalcSelection): string {
  return `${pick.homeName} vs ${pick.awayName} ${pick.playLabel}${outcomeTitle(pick.market, pick.outcome)}`
}

function oddsFormula(picks: CalcSelection[]): string {
  return picks.map((pick) => pick.odd).join(' × ')
}

function closePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = null
  }
  previewFile.value = null
}

async function saveDetailsToAlbum() {
  if (!groupedSelections.value.length || savingImage.value) return
  savingImage.value = true
  closePreview()
  try {
    await nextTick()
    const el = detailsExportRef.value
    if (!el) throw new Error('未找到导出内容')
    const filename = `投注方案-${todayDate()}.png`
    const result = await saveDomAsPng(el, filename)
    if (result.mode === 'shared') {
      message.success('请在分享菜单中选择「存储图像」')
    } else if (result.mode === 'preview') {
      previewFile.value = result.file
      previewUrl.value = result.url
    } else {
      message.success('图片已下载')
    }
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') return
    message.error(err instanceof Error ? err.message : '保存图片失败')
  } finally {
    savingImage.value = false
  }
}

/** Call share from a fresh tap — iOS needs user activation for the Photos sheet. */
async function sharePreviewImage() {
  const file = previewFile.value
  if (!file || sharingPreview.value) return
  sharingPreview.value = true
  try {
    // Do not await anything before share — preserves the tap's user activation.
    const shared = await sharePngFile(file)
    if (shared) {
      closePreview()
      message.success('请在分享菜单中选择「存储图像」')
      return
    }
    message.info('请长按上方图片，选择「存储到照片」')
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') return
    message.error(err instanceof Error ? err.message : '分享失败')
  } finally {
    sharingPreview.value = false
  }
}

watch(matchCount, (count) => {
  if (!count) showDetails.value = false
})

watch(showDetails, (open) => {
  if (!open) closePreview()
})

defineExpose({ openFormula, openDetails })
</script>

<template>
  <div class="bet-details-panel" :class="{ 'footer-only': props.footerOnly }">
    <div v-if="!props.footerOnly" class="scroll-fill">
      <n-scrollbar style="height: 100%;" trigger="hover">
        <BetSelectionList
          :groups="groupedSelections"
          empty-description="在「比赛」点选玩法后显示已选场次"
          @remove="removeFixture"
        />
      </n-scrollbar>
    </div>

    <n-flex vertical :size="8" class="details-footer">
      <div class="details-controls">
        <n-select
          v-model:value="fold"
          class="fold-select"
          size="small"
          :options="foldOptions"
          :disabled="!foldOptions.length"
          placeholder="过关方式"
        />
        <n-input-number
          v-model:value="multiplier"
          class="multiplier-input"
          size="small"
          :min="1"
          :max="99"
          button-placement="both"
        >
          <template #prefix>倍数</template>
        </n-input-number>
        <n-button
          class="save-button"
          size="small"
          type="primary"
          secondary
          :disabled="!matchCount"
          @click="openSave"
        >
          保存方案
        </n-button>
        <n-button
          v-if="props.footerOnly"
          size="small"
          type="primary"
          :disabled="!groupedSelections.length"
          @click="openDetails"
        >
          详情
        </n-button>
        <n-button
          class="clear-button"
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
      </div>

      <n-text depth="3">
        {{ foldModeLabel(fold) }} ·
        {{ result.betCount }} 注 {{ result.stakeYuan }} 元 · 预计奖金
        <n-text type="error" strong>
          {{ result.estimatedPrize || '—' }}
        </n-text>
        元
      </n-text>
    </n-flex>

    <n-modal
      v-model:show="showDetails"
      preset="card"
      title="投注详情"
      :bordered="false"
      to="body"
      :auto-focus="false"
      closable
      mask-closable
      :style="detailsModalStyle"
    >
      <template #header-extra>
        <n-button
          size="tiny"
          type="primary"
          secondary
          :loading="savingImage"
          :disabled="!groupedSelections.length"
          @click="saveDetailsToAlbum"
        >
          <template #icon>
            <n-icon :component="ImageOutline" />
          </template>
          保存到相册
        </n-button>
      </template>

      <div class="details-modal-body">
        <n-scrollbar style="height: 100%;" trigger="hover">
          <div ref="detailsExportRef" class="details-export">
            <BetSelectionList
              :groups="groupedSelections"
              @remove="removeFixture"
            />
          </div>
        </n-scrollbar>
      </div>
    </n-modal>

    <n-modal
      :show="!!previewUrl"
      preset="card"
      title="保存到相册"
      :bordered="false"
      to="body"
      :auto-focus="false"
      closable
      mask-closable
      :style="{
        width: 'min(400px, calc(100vw - 40px))',
        margin: 'auto',
      }"
      @update:show="(v: boolean) => { if (!v) closePreview() }"
    >
      <n-flex vertical :size="12" align="center">
        <img
          v-if="previewUrl"
          class="preview-image"
          :src="previewUrl"
          alt="投注方案"
        />
        <n-text depth="3" style="font-size: 12px; text-align: center;">
          上方已是生成好的图片。请点下方按钮，在分享菜单选「存储图像」；
          长按图中文字可能触发系统「实时文本」，不一定是保存。
        </n-text>
        <n-button
          type="primary"
          block
          :loading="sharingPreview"
          @click="sharePreviewImage"
        >
          存储到相册
        </n-button>
      </n-flex>
    </n-modal>

    <n-modal
      v-model:show="showFormula"
      preset="card"
      :title="`奖金算式 · ${foldModeLabel(fold)}`"
      :bordered="false"
      to="body"
      :auto-focus="false"
      closable
      mask-closable
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
      :auto-focus="false"
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

.details-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.fold-select {
  width: 84px;
  flex-shrink: 0;
}

.multiplier-input {
  flex: 1 1 110px;
  min-width: 0;
}

.details-controls :deep(.n-button) {
  flex-shrink: 0;
  padding-right: 8px;
  padding-left: 8px;
}

.bet-details-panel:not(.footer-only) .details-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
}

.bet-details-panel:not(.footer-only) .fold-select {
  width: auto;
  min-width: 0;
}

.bet-details-panel:not(.footer-only) .multiplier-input {
  grid-column: 2 / 4;
  min-width: 0;
}

.bet-details-panel:not(.footer-only) .save-button {
  grid-column: 1 / 3;
}

.bet-details-panel:not(.footer-only) .clear-button {
  grid-column: 3;
}

.footer-only .details-footer {
  border-top: none;
}

.details-modal-body {
  height: min(52vh, 480px);
  min-height: 0;
  overflow: hidden;
}

.details-export {
  background: var(--fa-bg-elevated);
}

.preview-image {
  display: block;
  width: 100%;
  max-height: min(52vh, 420px);
  object-fit: contain;
  border-radius: 6px;
  background: var(--fa-bg-soft);
  -webkit-touch-callout: default;
  user-select: none;
}

.formula-modal-body {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  height: min(70vh, 640px);
  min-height: 0;
}

@media (min-width: 768px) {
  .details-modal-body {
    height: min(70vh, 640px);
  }
}
</style>
