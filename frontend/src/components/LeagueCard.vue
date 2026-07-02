<script setup lang="ts">
import type { LeagueSummaryResponse } from '@/api/types'

defineProps<{
  league: LeagueSummaryResponse
}>()
</script>

<template>
  <n-card
    hoverable
    class="league-card"
    :title="league.league_name"
    @click="$router.push({ name: 'fixtures', params: { leagueId: league.league_id } })"
  >
    <div class="league-meta">
      <span v-if="league.country">{{ league.country }}</span>
      <n-tag size="small" type="info" :bordered="false">
        今日 {{ league.today_fixtures_count }} 场
      </n-tag>
    </div>
  </n-card>
</template>

<style scoped>
.league-card {
  cursor: pointer;
  height: 100%;
}

.league-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #666;
}
</style>
