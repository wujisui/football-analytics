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
  referenceAdjustedEv?: number | null
  referenceProbability?: number | null
  referenceAlignment?: string | null
  referenceReason?: string | null
}>()

/** 后端在四个玩法都拿不到方向时写入的占位，见 decision.select_reference_candidate。 */
const REFERENCE_UNAVAILABLE = '数据不足'

const ALIGNMENT_LABELS: Record<string, string> = {
  aligned_strong: '盘口强一致',
  aligned_weak: '盘口一致',
  unknown: '盘口方向不明确',
  reverse_weak: '逆向推荐（弱）',
  reverse_strong: '逆向推荐（强）',
}

function percent(value: number): string {
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
}

const isPhone = useIsPhone()
const rating = computed(() => normalizeQualityRating(props.value))

/** 槽位很窄：只给方向与调整后 EV，其余明细留给 tooltip。 */
const label = computed(() => {
  if (rating.value != null) return ''
  const lean = (props.referenceLean || '').trim()
  if (!lean) return ''
  if (lean === REFERENCE_UNAVAILABLE) return '参考数据不足'
  if (props.referenceAdjustedEv == null) return `参考 ${lean} · EV 待定`
  return `参考 ${lean} ${percent(props.referenceAdjustedEv)}`
})

const detail = computed(() => {
  const parts: string[] = []
  const lean = (props.referenceLean || '').trim()
  if (lean && lean !== REFERENCE_UNAVAILABLE) parts.push(`参考方向：${lean}`)
  if (props.referenceProbability != null) {
    parts.push(`校准概率：${(props.referenceProbability * 100).toFixed(1)}%`)
  }
  parts.push(
    props.referenceEv == null ? 'EV：数据不足' : `EV：${percent(props.referenceEv)}`,
  )
  if (props.referenceAdjustedEv != null) {
    parts.push(`方向修正后：${percent(props.referenceAdjustedEv)}`)
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
      <span class="strength-slot reference">{{ label }}</span>
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

.reference {
  flex-shrink: 1;
  overflow: hidden;
  max-width: min(100%, 220px);
  color: var(--n-text-color-3);
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
