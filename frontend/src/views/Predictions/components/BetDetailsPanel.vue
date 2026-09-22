<script setup lang="ts">
import { ImageOutline, TrashOutline } from '@vicons/ionicons5'
import { useMessage } from 'naive-ui'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
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
import { saveDomAsPng, sharePngFile } from '@/utils/saveDomImage'
import { todayDate } from '@/utils/homeDateStrip'

const props = defineProps<{
  /** Drawer 的挂载容器：内容区，不是浏览器视口。缺省时退回 body。 */
  drawerTarget?: HTMLElement | null
}>()

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
const savingPlan = ref(false)
const savingImage = ref(false)
const detailsExportRef = ref<HTMLElement | null>(null)
const previewUrl = ref<string | null>(null)
const previewFile = ref<File | null>(null)
const sharingPreview = ref(false)
/** 抽屉高度跟着内容走；Naive 的 `height: auto` 不会把上限传给正文，只能量出像素值。 */
const drawerHeight = ref<number>()
let drawerResizeObserver: ResizeObserver | null = null

const detailsDrawerTarget = computed(() => props.drawerTarget ?? 'body')

function syncDrawerHeight() {
  const exportEl = detailsExportRef.value
  if (!exportEl) return
  const drawerEl = exportEl.closest('.n-drawer')
  const headerHeight =
    drawerEl?.querySelector('.n-drawer-header')?.getBoundingClientRect()
      .height ?? 0
  const natural = headerHeight + exportEl.getBoundingClientRect().height
  const limit = (props.drawerTarget?.clientHeight ?? window.innerHeight) * 0.8
  drawerHeight.value = Math.round(Math.min(natural, limit))
}

function toggleDetails() {
  if (showDetails.value) {
    showDetails.value = false
    return
  }
  if (!groupedSelections.value.length) return
  showDetails.value = true
}

function openFormula() {
  if (result.value.combos.length) showFormula.value = true
}

function openSave() {
  if (!matchCount.value) return
  if (!requireLogin()) return
  saveName.value = foldModeLabel(fold.value)
  showSave.value = true
}

async function confirmSave(): Promise<boolean> {
  if (savingPlan.value) return false
  if (!requireLogin()) return false
  if (!selections.value.length) return false
  savingPlan.value = true
  try {
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
  } finally {
    savingPlan.value = false
  }
}

/** 输入框回车 = 点「保存」（naive dialog 不会默认绑 Enter） */
function onSaveNameEnter(e: KeyboardEvent) {
  if (e.isComposing) return
  if (!matchCount.value) return
  e.preventDefault()
  void confirmSave()
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

watch(showDetails, async (open) => {
  if (!open) {
    closePreview()
    drawerResizeObserver?.disconnect()
    drawerResizeObserver = null
    return
  }
  await nextTick()
  syncDrawerHeight()
  // 已选场次增减、窗口变化都要重新量：两者都不受抽屉高度影响，不会来回抖。
  drawerResizeObserver = new ResizeObserver(syncDrawerHeight)
  if (detailsExportRef.value) drawerResizeObserver.observe(detailsExportRef.value)
  if (props.drawerTarget) drawerResizeObserver.observe(props.drawerTarget)
})

onBeforeUnmount(() => {
  drawerResizeObserver?.disconnect()
  drawerResizeObserver = null
})
</script>

<template>
  <div class="bet-details-panel" :class="{ phone: isPhone }">
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
          :show-button="false"
          button-placement="both"
        >
          <template #suffix>倍</template>
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
          size="small"
          type="primary"
          :disabled="!groupedSelections.length"
          :aria-label="showDetails ? '收起投注详情' : '展开投注详情'"
          @click="toggleDetails"
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

    <n-drawer
      v-model:show="showDetails"
      placement="bottom"
      :height="drawerHeight"
      :to="detailsDrawerTarget"
      :block-scroll="false"
      display-directive="if"
      class="bet-details-drawer"
    >
      <n-drawer-content :native-scrollbar="false" body-content-style="padding: 0;">
        <!-- 关闭交给工具条的箭头与遮罩，标题行让给这两个操作。 -->
        <template #header>
          <div class="drawer-header">
            <n-text strong>投注详情</n-text>
            <n-flex :size="8" :wrap="false">
              <n-button
                size="tiny"
                type="primary"
                secondary
                :disabled="!result.combos.length"
                @click="openFormula"
              >
                奖金算式
              </n-button>
              <n-button
                v-if="isPhone"
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
            </n-flex>
          </div>
        </template>

        <div ref="detailsExportRef" class="details-export">
          <BetSelectionList :groups="groupedSelections" @remove="removeFixture" />
        </div>
      </n-drawer-content>
    </n-drawer>

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
      :positive-button-props="{ disabled: !matchCount || savingPlan, loading: savingPlan }"
      :negative-button-props="{ disabled: savingPlan }"
      :closable="!savingPlan"
      :close-on-esc="!savingPlan"
      :mask-closable="!savingPlan"
      @positive-click="() => confirmSave()"
    >
      <n-space vertical :size="10">
        <n-input
          v-model:value="saveName"
          maxlength="40"
          show-count
          placeholder="方案名称"
          @keydown.enter="onSaveNameEnter"
        />
        <n-text depth="3" style="font-size: 12px;">
          保存后可在「我的 → 我的方案」按赛程日回溯命中情况。
          <n-button
            text
            type="primary"
            size="tiny"
            :loading="savingPlan"
            :disabled="!matchCount || savingPlan"
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
  width: min(var(--calc-panel-width, 400px), 100%);
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
  background-color: var(--fa-bg-elevated);
}

.details-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-width: 0;
}

.fold-select {
  width: 84px;
  flex-shrink: 0;
}

.multiplier-input {
  flex: 0 0 78px;
  min-width: 0;
}

.details-controls :deep(.n-button) {
  flex-shrink: 0;
  padding-right: 8px;
  padding-left: 8px;
}

.save-button {
  padding-right: 12px;
  padding-left: 12px;
}

/* 手机让三个按钮均分剩余宽度撑满整行，点击区域才够大。 */
.bet-details-panel.phone .details-controls :deep(.n-button) {
  flex: 1 1 0;
}

/* 与摘要条同宽同左边缘；高度由 syncDrawerHeight 量出来。
   不能改 transform，那是 Naive 的滑入动画。 */
:global(.bet-details-drawer.n-drawer--bottom-placement) {
  width: min(var(--calc-panel-width, 400px), 100%);
  margin: 0;
}


.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.details-export {
  background: var(--fa-bg-elevated);
}

.preview-image {
  display: block;
  width: 100%;
  max-height: min(52vh, 420px);
  object-fit: contain;
  border-radius: var(--fa-radius-card);
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

</style>
