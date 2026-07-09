<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { fetchFixtureAnalysis } from '@/api/fixtures'
import type { FixtureResponse, LineupPlayer, PrematchPackage } from '@/api/types'
import ProbabilityChart from '@/components/ProbabilityChart.vue'

const props = defineProps<{
  fixtureId: string
}>()

const router = useRouter()

const fixture = ref<FixtureResponse | null>(null)
const loading = ref(true)
const error = ref('')

const fixtureIdNumber = computed(() => Number(props.fixtureId))
const pkg = computed<PrematchPackage | null>(() => fixture.value?.analysis.package ?? null)

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString('zh-CN')
}

function confidenceType(confidence: string): 'success' | 'warning' | 'error' | 'default' {
  if (confidence === '高') return 'success'
  if (confidence === '中') return 'warning'
  if (confidence === '低') return 'error'
  return 'default'
}

function playerLabel(p: LineupPlayer): string {
  const num = p.number != null ? `${p.number}. ` : ''
  const pos = p.pos ? ` (${p.pos})` : ''
  return `${num}${p.name}${pos}`
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

        <n-card v-if="pkg?.odds" title="赛前赔率（1X2）">
          <template v-if="pkg.odds.available && pkg.odds.match_winner">
            <n-descriptions :column="2" label-placement="left" bordered>
              <n-descriptions-item label="公司">
                {{ pkg.odds.match_winner.bookmaker || '-' }}
              </n-descriptions-item>
              <n-descriptions-item label="主胜">{{ pkg.odds.match_winner.home ?? '-' }}</n-descriptions-item>
              <n-descriptions-item label="平局">{{ pkg.odds.match_winner.draw ?? '-' }}</n-descriptions-item>
              <n-descriptions-item label="客胜">{{ pkg.odds.match_winner.away ?? '-' }}</n-descriptions-item>
            </n-descriptions>
          </template>
          <n-empty v-else description="暂无赔率数据（可能尚未开盘或未拉取）" />
        </n-card>

        <n-card v-if="pkg" title="历史交锋">
          <template v-if="pkg.head_to_head.played > 0">
            <p class="summary">
              近 {{ pkg.head_to_head.played }} 场：主队胜 {{ pkg.head_to_head.home_wins }} /
              平 {{ pkg.head_to_head.draws }} / 客队胜 {{ pkg.head_to_head.away_wins }}
            </p>
            <n-ul>
              <n-li v-for="(m, idx) in pkg.head_to_head.matches" :key="idx">
                {{ m.date || '' }} · {{ m.home }} {{ m.score }} {{ m.away }}
              </n-li>
            </n-ul>
          </template>
          <n-empty v-else description="暂无交锋记录" />
        </n-card>

        <n-grid v-if="pkg" :cols="2" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
          <n-gi span="2 m:1">
            <n-card :title="`${fixture.home_team_name} 近况`">
              <template v-if="pkg.home_form.played > 0">
                <p class="summary">
                  {{ pkg.home_form.form || '' }} ·
                  {{ pkg.home_form.wins }}胜 {{ pkg.home_form.draws }}平 {{ pkg.home_form.losses }}负
                </p>
                <n-ul>
                  <n-li v-for="(m, idx) in pkg.home_form.matches" :key="idx">
                    {{ m.result }} · {{ m.home }} {{ m.score }} {{ m.away }}
                  </n-li>
                </n-ul>
              </template>
              <n-empty v-else description="暂无近况" />
            </n-card>
          </n-gi>
          <n-gi span="2 m:1">
            <n-card :title="`${fixture.away_team_name} 近况`">
              <template v-if="pkg.away_form.played > 0">
                <p class="summary">
                  {{ pkg.away_form.form || '' }} ·
                  {{ pkg.away_form.wins }}胜 {{ pkg.away_form.draws }}平 {{ pkg.away_form.losses }}负
                </p>
                <n-ul>
                  <n-li v-for="(m, idx) in pkg.away_form.matches" :key="idx">
                    {{ m.result }} · {{ m.home }} {{ m.score }} {{ m.away }}
                  </n-li>
                </n-ul>
              </template>
              <n-empty v-else description="暂无近况" />
            </n-card>
          </n-gi>
        </n-grid>

        <n-grid v-if="pkg" :cols="2" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
          <n-gi span="2 m:1">
            <n-card :title="`阵容 · ${fixture.home_team_name}`">
              <template v-if="pkg.lineups.available && pkg.lineups.home">
                <p class="summary">
                  阵型 {{ pkg.lineups.home.formation || pkg.home_formation || '-' }}
                  <span v-if="pkg.lineups.home.coach"> · 教练 {{ pkg.lineups.home.coach }}</span>
                </p>
                <n-h4>首发</n-h4>
                <n-ul>
                  <n-li v-for="(p, idx) in pkg.lineups.home.start_xi" :key="idx">
                    {{ playerLabel(p) }}
                  </n-li>
                </n-ul>
                <n-h4>替补</n-h4>
                <n-ul v-if="pkg.lineups.home.substitutes.length">
                  <n-li v-for="(p, idx) in pkg.lineups.home.substitutes" :key="idx">
                    {{ playerLabel(p) }}
                  </n-li>
                </n-ul>
                <n-empty v-else description="暂无替补名单" />
              </template>
              <n-empty v-else description="阵容尚未公布或未拉取" />
            </n-card>
          </n-gi>
          <n-gi span="2 m:1">
            <n-card :title="`阵容 · ${fixture.away_team_name}`">
              <template v-if="pkg.lineups.available && pkg.lineups.away">
                <p class="summary">
                  阵型 {{ pkg.lineups.away.formation || pkg.away_formation || '-' }}
                  <span v-if="pkg.lineups.away.coach"> · 教练 {{ pkg.lineups.away.coach }}</span>
                </p>
                <n-h4>首发</n-h4>
                <n-ul>
                  <n-li v-for="(p, idx) in pkg.lineups.away.start_xi" :key="idx">
                    {{ playerLabel(p) }}
                  </n-li>
                </n-ul>
                <n-h4>替补</n-h4>
                <n-ul v-if="pkg.lineups.away.substitutes.length">
                  <n-li v-for="(p, idx) in pkg.lineups.away.substitutes" :key="idx">
                    {{ playerLabel(p) }}
                  </n-li>
                </n-ul>
                <n-empty v-else description="暂无替补名单" />
              </template>
              <n-empty v-else description="阵容尚未公布或未拉取" />
            </n-card>
          </n-gi>
        </n-grid>

        <n-grid v-if="pkg" :cols="2" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
          <n-gi span="2 m:1">
            <n-card :title="`伤病 · ${fixture.home_team_name}`">
              <n-ul v-if="pkg.injuries.home.length">
                <n-li v-for="(p, idx) in pkg.injuries.home" :key="idx">
                  {{ p.player_name }}
                  <span v-if="p.reason"> — {{ p.reason }}</span>
                  <span v-else-if="p.type"> — {{ p.type }}</span>
                </n-li>
              </n-ul>
              <n-empty v-else description="无伤病信息" />
            </n-card>
          </n-gi>
          <n-gi span="2 m:1">
            <n-card :title="`伤病 · ${fixture.away_team_name}`">
              <n-ul v-if="pkg.injuries.away.length">
                <n-li v-for="(p, idx) in pkg.injuries.away" :key="idx">
                  {{ p.player_name }}
                  <span v-if="p.reason"> — {{ p.reason }}</span>
                  <span v-else-if="p.type"> — {{ p.type }}</span>
                </n-li>
              </n-ul>
              <n-empty v-else description="无伤病信息" />
            </n-card>
          </n-gi>
        </n-grid>
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

.summary {
  margin: 0 0 12px;
  color: #555;
}
</style>
