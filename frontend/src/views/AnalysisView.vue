<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { fetchFixtureAnalysis } from '@/api/fixtures'
import type { FixtureResponse } from '@/api/types'
import ProbabilityChart from '@/components/ProbabilityChart.vue'

const props = defineProps<{
  fixtureId: string
}>()

const router = useRouter()

const fixture = ref<FixtureResponse | null>(null)
const loading = ref(true)
const error = ref('')

const fixtureIdNumber = computed(() => Number(props.fixtureId))

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString('zh-CN')
}

function confidenceType(confidence: string): 'success' | 'warning' | 'error' | 'default' {
  if (confidence === '高') return 'success'
  if (confidence === '中') return 'warning'
  if (confidence === '低') return 'error'
  return 'default'
}

async function loadAnalysis() {
  loading.value = true
  error.value = ''
  fixture.value = null

  if (Number.isNaN(fixtureIdNumber.value)) {
    error.value = '无效的比赛 ID'
    loading.value = false
    return
  }

  try {
    fixture.value = await fetchFixtureAnalysis(fixtureIdNumber.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载分析失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadAnalysis)
watch(() => props.fixtureId, loadAnalysis)
</script>

<template>
  <div class="page">
    <n-page-header
      :title="fixture ? `${fixture.home_team_name} vs ${fixture.away_team_name}` : '比赛分析'"
      :subtitle="fixture ? `${fixture.league_name} · ${formatDateTime(fixture.fixture_date)}` : ''"
      @back="router.back()"
    />

    <n-spin :show="loading">
      <n-alert v-if="error" type="error" :title="error" class="state-block" />

      <template v-else-if="fixture">
        <n-card title="胜平负概率">
          <ProbabilityChart :probabilities="fixture.analysis.probabilities" />
        </n-card>

        <n-card title="分析结论">
          <n-descriptions :column="2" label-placement="left" bordered>
            <n-descriptions-item label="推荐">
              <n-tag type="primary">{{ fixture.analysis.recommendation }}</n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="置信度">
              <n-tag :type="confidenceType(fixture.analysis.confidence)">
                {{ fixture.analysis.confidence }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="比赛状态">{{ fixture.status }}</n-descriptions-item>
            <n-descriptions-item label="数据来源">{{ fixture.analysis.data_source }}</n-descriptions-item>
            <n-descriptions-item label="分析时间">
              {{ formatDateTime(fixture.analysis.analyzed_at) }}
            </n-descriptions-item>
            <n-descriptions-item label="缓存状态">{{ fixture.analysis.cache_status }}</n-descriptions-item>
          </n-descriptions>
        </n-card>
      </template>
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
