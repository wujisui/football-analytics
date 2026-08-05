<script setup lang="ts">
import { StatsChartOutline } from '@vicons/ionicons5'

import PageToolbarSearch from '@/components/PageToolbarSearch.vue'
import LeagueFilterTrigger from '@/layouts/components/LeagueFilterTrigger.vue'
import type { LeagueFilterOption } from '@/api/leagues'
import { useIsPhone } from '@/composables/useMediaQuery'

withDefaults(
  defineProps<{
    filterOptions: LeagueFilterOption[]
    trackedIds: number[]
    filterActive: boolean
    /** Phone: open 当日统计 modal from the list toolbar. */
    showDayStats?: boolean
  }>(),
  { showDayStats: false },
)

const teamSearch = defineModel<string>('teamSearch', { required: true })
const isPhone = useIsPhone()

const emit = defineEmits<{
  confirmFilter: [ids: number[]]
  openDayStats: []
}>()
</script>

<template>
  <n-flex :wrap="false" align="center" :size="8" style="width: 100%; min-width: 0;">
    <PageToolbarSearch
      v-model="teamSearch"
      style="flex: 1; width: auto; min-width: 0; max-width: none;"
    />
    <n-button
      v-if="showDayStats"
      size="small"
      type="primary"
      secondary
      aria-label="当日统计"
      @click="emit('openDayStats')"
    >
      <template #icon>
        <n-icon :component="StatsChartOutline" />
      </template>
      当日统计
    </n-button>
    <!-- Desktop: same popover as calculator sider; phone keeps modal for tap targets. -->
    <LeagueFilterTrigger
      :drawer-mode="isPhone"
      :options="filterOptions"
      :tracked-ids="trackedIds"
      :filter-active="filterActive"
      @confirm="emit('confirmFilter', $event)"
    />
  </n-flex>
</template>
