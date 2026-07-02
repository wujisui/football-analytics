<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { fetchTodayFixtures } from '@/api/fixtures'
import type { FixtureResponse } from '@/api/types'
import FixtureList from '@/components/FixtureList.vue'

const props = defineProps<{
  leagueId: string
}>()

const router = useRouter()

const fixtures = ref<FixtureResponse[]>([])
const date = ref('')
const loading = ref(true)
const error = ref('')

const leagueIdNumber = computed(() => Number(props.leagueId))
const leagueName = computed(() => fixtures.value[0]?.league_name || `联赛 ${props.leagueId}`)

async function loadFixtures() {
  loading.value = true
  error.value = ''
  fixtures.value = []
  date.value = ''

  if (Number.isNaN(leagueIdNumber.value)) {
    error.value = '无效的联赛 ID'
    loading.value = false
    return
  }

  try {
    const data = await fetchTodayFixtures(leagueIdNumber.value)
    fixtures.value = data.fixtures
    date.value = data.date
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载赛程失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadFixtures)
watch(() => props.leagueId, loadFixtures)
</script>

<template>
  <div class="page">
    <n-page-header
      :title="leagueName"
      :subtitle="date ? `今日赛程 · ${date}` : '今日赛程'"
      @back="router.push({ name: 'leagues' })"
    />

    <n-spin :show="loading">
      <n-alert v-if="error" type="error" :title="error" class="state-block" />

      <n-empty
        v-else-if="!loading && fixtures.length === 0"
        description="今日暂无比赛，请先在后端执行 fetch-today"
        class="state-block"
      />

      <FixtureList v-else :fixtures="fixtures" />
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
