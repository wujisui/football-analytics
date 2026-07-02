<script setup lang="ts">
import type { FixtureResponse } from '@/api/types'

defineProps<{
  fixtures: FixtureResponse[]
}>()

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function confidenceType(confidence: string): 'success' | 'warning' | 'error' | 'default' {
  if (confidence === '高') return 'success'
  if (confidence === '中') return 'warning'
  if (confidence === '低') return 'error'
  return 'default'
}
</script>

<template>
  <n-table :bordered="false" :single-line="false" class="fixture-table">
    <thead>
      <tr>
        <th>时间</th>
        <th>对阵</th>
        <th>状态</th>
        <th>推荐</th>
        <th>置信度</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="fixture in fixtures"
        :key="fixture.fixture_id"
        class="fixture-row"
        @click="$router.push({ name: 'analysis', params: { fixtureId: fixture.fixture_id } })"
      >
        <td>{{ formatTime(fixture.fixture_date) }}</td>
        <td>
          <strong>{{ fixture.home_team_name }}</strong>
          <span class="vs">vs</span>
          <strong>{{ fixture.away_team_name }}</strong>
        </td>
        <td>{{ fixture.status }}</td>
        <td>
          <n-tag size="small" type="primary">{{ fixture.analysis.recommendation }}</n-tag>
        </td>
        <td>
          <n-tag size="small" :type="confidenceType(fixture.analysis.confidence)">
            {{ fixture.analysis.confidence }}
          </n-tag>
        </td>
      </tr>
    </tbody>
  </n-table>
</template>

<style scoped>
.fixture-table {
  width: 100%;
}

.fixture-row {
  cursor: pointer;
}

.fixture-row:hover {
  background: rgba(24, 160, 88, 0.06);
}

.vs {
  margin: 0 8px;
  color: #999;
}
</style>
