<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'

import { fetchAuthMe, saveLeagueDefaults } from '@/api/auth'
import { fetchLeagueCatalog, type LeagueCatalogItem } from '@/api/leagues'
import { useAuthSession } from '@/composables/useAuthSession'
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineVipLeagues' })

const message = useMessage()
const { syncAuthUser } = useAuthSession()
const loading = ref(true)
const saving = ref(false)
const leagues = ref<LeagueCatalogItem[]>([])
const selectedIds = ref<number[]>([])

const groups = computed(() => {
  const buckets = new Map<string, LeagueCatalogItem[]>()
  for (const league of leagues.value) {
    const key = league.country?.trim() || '其他'
    const list = buckets.get(key) ?? []
    list.push(league)
    buckets.set(key, list)
  }
  return [...buckets.entries()].map(([country, items]) => ({ country, items }))
})

async function load() {
  loading.value = true
  try {
    const catalog = await fetchLeagueCatalog()
    const me = await fetchAuthMe()
    syncAuthUser(me)
    leagues.value = catalog.leagues
    const saved = me.league_default_ids
    const known = new Set(catalog.leagues.map((item) => item.league_id))
    selectedIds.value = saved == null
      ? catalog.leagues.filter((item) => item.hot).map((item) => item.league_id)
      : saved.filter((id) => known.has(id))
  } catch (err) {
    message.error(err instanceof Error ? err.message : '联赛目录加载失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const me = await saveLeagueDefaults(selectedIds.value)
    syncAuthUser(me)
    message.success('已保存默认勾选')
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <MineSectionBody>
    <n-alert type="info" :bordered="false">
      这里只影响本账号打开比赛和赛程时的默认勾选，不改变全站热门联赛，也不改变定时拉盘范围。某一天已经手动确认过的勾选仍然优先。
    </n-alert>
    <n-spin :show="loading">
      <n-checkbox-group v-model:value="selectedIds">
        <section v-for="group in groups" :key="group.country" class="vip-league-group">
          <h3 class="vip-league-country">{{ group.country }}</h3>
          <div class="vip-league-grid">
            <n-checkbox
              v-for="item in group.items"
              :key="item.league_id"
              :value="item.league_id"
              :label="item.league_name"
            />
          </div>
        </section>
      </n-checkbox-group>
      <n-empty v-if="!loading && !leagues.length" description="目录为空" />
    </n-spin>
    <n-flex justify="end">
      <n-button type="primary" :loading="saving" :disabled="loading" @click="save">
        保存
      </n-button>
    </n-flex>
  </MineSectionBody>
</template>

<style scoped>
.vip-league-group + .vip-league-group {
  margin-top: 16px;
}

.vip-league-country {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}

.vip-league-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px 12px;
}
</style>
