<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchLeagues } from '@/api/leagues'
import type { LeagueSummaryResponse } from '@/api/types'
import LeagueCard from '@/components/LeagueCard.vue'

const leagues = ref<LeagueSummaryResponse[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const data = await fetchLeagues()
    leagues.value = data.leagues
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载联赛失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <n-page-header title="联赛列表" subtitle="选择联赛查看今日赛程与分析" />

    <n-spin :show="loading">
      <n-alert v-if="error" type="error" :title="error" class="state-block" />

      <n-empty
        v-else-if="!loading && leagues.length === 0"
        description="暂无联赛数据，请先在后端执行 fetch-leagues"
        class="state-block"
      />

      <n-grid v-else :cols="3" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
        <n-gi v-for="league in leagues" :key="league.league_id" span="3 m:1 l:1">
          <LeagueCard :league="league" />
        </n-gi>
      </n-grid>
    </n-spin>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.state-block {
  margin-top: 24px;
}
</style>
