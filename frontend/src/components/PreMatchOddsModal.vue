<script setup lang="ts">
import { watch } from 'vue'
import { useRoute } from 'vue-router'

import PreMatchOddsTable from '@/components/PreMatchOddsTable.vue'
import type { DetailFrom } from '@/utils/detailNav'
import type { OddsLike } from '@/utils/oddsDisplay'

/** 手机列表点推荐/概率区弹出的赛前盘口（比赛 / 关注共用）。 */
const props = withDefaults(
  defineProps<{
    show: boolean
    odds: OddsLike
    fixtureId: number
    from?: DetailFrom
    date?: string | null
  }>(),
  {
    from: 'predictions',
    date: null,
  },
)

const emit = defineEmits<{
  'update:show': [value: boolean]
}>()

const route = useRoute()

/**
 * 表内「指数」会跳详情，但宿主列表在 keep-alive 里不卸载，
 * 弹窗 teleport 到 body 后会盖在详情页上，所以路由一变就关掉。
 */
watch(
  () => route.fullPath,
  () => {
    if (props.show) emit('update:show', false)
  },
)
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="赛前盘口"
    to="body"
    :auto-focus="false"
    :style="{ width: 'min(360px, calc(100vw - 24px))' }"
    :segmented="{ content: true, footer: false }"
    @update:show="emit('update:show', $event)"
  >
    <PreMatchOddsTable
      :odds="odds"
      link-middle-to-detail
      :fixture-id="fixtureId"
      :from="from"
      :date="date"
    />
  </n-modal>
</template>
