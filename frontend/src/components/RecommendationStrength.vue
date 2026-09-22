<script setup lang="ts">
import { computed } from 'vue'

import { useIsPhone } from '@/composables/useMediaQuery'
import { normalizeQualityRating } from '@/utils/qualityRating'

const props = defineProps<{
  /** 1–5 星推荐强度；只有当天日推场次才有。 */
  value?: number | null
  /** 非日推场次在同一位置展示的每场参考。 */
  referenceLean?: string | null
  referenceEv?: number | null
  referenceSource?: string | null
  referenceProbability?: number | null
  referenceAlignment?: string | null
  referenceReason?: string | null
}>()

/** 后端在四个玩法都拿不到方向时写入的占位，见 decision.build_match_decision。 */
const REFERENCE_UNAVAILABLE = '数据不足'

const ALIGNMENT_LABELS: Record<string, string> = {
  aligned_strong: '盘口强一致',
  aligned_weak: '盘口一致',
  unknown: '盘口方向不明确',
  reverse_weak: '逆向推荐（弱）',
  reverse_strong: '逆向推荐（强）',
}

const SOURCE_LABELS: Record<string, string> = {
  market: '概率来源：盘口去水（市场基线，未跑赢市场的模型不参与）',
  model: '概率来源：已通过时间留出验证的模型',
}

function percent(value: number): string {
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
}

const isPhone = useIsPhone()
const rating = computed(() => normalizeQualityRating(props.value))

/**
 * 槽位很窄：方向已由行内标签高亮，这里只给命中概率，否则手机上会换行。
 * 方向与其余明细留给 tooltip。
 */
const label = computed(() => {
  if (rating.value != null) return ''
  const lean = (props.referenceLean || '').trim()
  if (!lean) return ''
  if (lean === REFERENCE_UNAVAILABLE) return '数据不足'
  if (props.referenceProbability == null) return lean
  return `${(props.referenceProbability * 100).toFixed(1)}%`
})

/**
 * 概率与行内被高亮的那个玩法标签同色，视觉上把「这个百分比属于哪一注」连起来。
 * 「数据不足」「只有方向」不是高亮，保持弱化。
 */
const showsProbability = computed(
  () => !!label.value && props.referenceProbability != null,
)

const detail = computed(() => {
  const parts: string[] = []
  const lean = (props.referenceLean || '').trim()
  if (lean && lean !== REFERENCE_UNAVAILABLE) parts.push(`参考方向：${lean}`)
  if (props.referenceProbability != null) {
    parts.push(`命中概率：${(props.referenceProbability * 100).toFixed(1)}%`)
  }
  const source = SOURCE_LABELS[props.referenceSource || '']
  if (source) parts.push(source)
  if (props.referenceEv != null) {
    // 概率来自所投的那块盘时，EV 恒为负，负的幅度就是庄家抽水。
    parts.push(`EV：${percent(props.referenceEv)}（含抽水，仅供审计）`)
  }
  const alignment = ALIGNMENT_LABELS[props.referenceAlignment || '']
  if (alignment) parts.push(alignment)
  const reason = (props.referenceReason || '').trim()
  if (reason) parts.push(reason)
  return parts.join('\n')
})
</script>

<template>
  <n-rate
    v-if="rating != null"
    class="strength-slot"
    readonly
    allow-half
    :size="14"
    :count="5"
    :value="rating"
    :aria-label="`推荐强度 ${rating} / 5`"
  />
  <n-tooltip
    v-else-if="label"
    :disabled="isPhone"
    trigger="hover"
    placement="top"
    :delay="200"
  >
    <template #trigger>
      <n-text
        class="strength-slot reference"
        :type="showsProbability ? 'success' : 'default'"
        :depth="showsProbability ? undefined : 3"
      >
        {{ label }}
      </n-text>
    </template>
    <span class="reference-detail">{{ detail }}</span>
  </n-tooltip>
</template>

<style scoped>
/* 槽位自己不可点（点击已 stop），落在可点整行里也别显示小手 */
.strength-slot {
  flex-shrink: 0;
  cursor: default;
}

/* 颜色交给 n-text 的 type / depth，按主题解析，勿在此覆盖 */
.reference {
  flex-shrink: 1;
  overflow: hidden;
  max-width: min(100%, 220px);
  font-size: 12px;
  line-height: 1.4;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* 浮层被 teleport 到 body，scoped 属性仍在，多行明细按换行排版 */
.reference-detail {
  display: block;
  white-space: pre-line;
}
</style>
