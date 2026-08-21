<script setup lang="ts">
import { TrophyOutline } from '@vicons/ionicons5'
import { useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'

import {
  fetchHotLeaguesSetting,
  updateHotLeaguesSetting,
  type HotLeagueItem,
} from '@/api/admin'
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineHotLeagues' })

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const leagues = ref<HotLeagueItem[]>([])
const selectedIds = ref<number[]>([])
const defaultIds = ref<number[]>([])

const GROUP_ORDER = [
  '五大联赛',
  '欧洲杯赛',
  '其他欧洲',
  '国际赛事',
  '洲际杯赛',
  '美洲',
  '亚洲及大洋洲',
  '其他',
] as const

type LeagueGroup = (typeof GROUP_ORDER)[number]

const LEAGUE_GROUP: Record<number, Exclude<LeagueGroup, '其他'>> = {
  39: '五大联赛',
  140: '五大联赛',
  78: '五大联赛',
  135: '五大联赛',
  61: '五大联赛',
  2: '欧洲杯赛',
  3: '欧洲杯赛',
  848: '欧洲杯赛',
  40: '其他欧洲',
  79: '其他欧洲',
  62: '其他欧洲',
  88: '其他欧洲',
  89: '其他欧洲',
  94: '其他欧洲',
  179: '其他欧洲',
  103: '其他欧洲',
  113: '其他欧洲',
  1: '国际赛事',
  4: '国际赛事',
  5: '国际赛事',
  9: '国际赛事',
  6: '国际赛事',
  7: '国际赛事',
  22: '国际赛事',
  10: '洲际杯赛',
  17: '洲际杯赛',
  13: '洲际杯赛',
  11: '洲际杯赛',
  16: '洲际杯赛',
  71: '美洲',
  128: '美洲',
  253: '美洲',
  169: '亚洲及大洋洲',
  98: '亚洲及大洋洲',
  292: '亚洲及大洋洲',
  188: '亚洲及大洋洲',
  307: '亚洲及大洋洲',
}

const selectedCount = computed(() => selectedIds.value.length)

const leagueGroups = computed(() => {
  const buckets = new Map<LeagueGroup, HotLeagueItem[]>()
  for (const item of leagues.value) {
    const group = LEAGUE_GROUP[item.league_id] ?? '其他'
    const list = buckets.get(group)
    if (list) list.push(item)
    else buckets.set(group, [item])
  }
  return GROUP_ORDER.flatMap((title) => {
    const items = buckets.get(title)
    if (!items?.length) return []
    const selectedSet = new Set(selectedIds.value.map(Number))
    const selected = items.filter((item) => selectedSet.has(item.league_id)).length
    return [{ title, items, selected }]
  })
})

function applySetting(data: Awaited<ReturnType<typeof fetchHotLeaguesSetting>>) {
  leagues.value = data.leagues
  selectedIds.value = [...data.league_ids]
  defaultIds.value = [...data.default_league_ids]
}

async function loadSetting() {
  loading.value = true
  try {
    applySetting(await fetchHotLeaguesSetting())
  } catch (err) {
    message.error(err instanceof Error ? err.message : '读取热门联赛失败')
  } finally {
    loading.value = false
  }
}

function restoreDefault() {
  selectedIds.value = [...defaultIds.value]
}

async function save() {
  saving.value = true
  try {
    applySetting(await updateHotLeaguesSetting(selectedIds.value.map(Number)))
    message.success(
      selectedIds.value.length
        ? `已保存 ${selectedIds.value.length} 项热门，下次定时同步按此拉取盘口`
        : '已保存：热门为空，定时任务将不再拉取赛前盘口',
    )
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存热门联赛失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadSetting()
})
</script>

<template>
  <MineSectionBody>
    <n-flex vertical :size="12">
      <n-card size="small" title="热门联赛" :bordered="false">
        <n-list>
          <n-list-item>
            <template #prefix>
              <n-icon :component="TrophyOutline" :size="20" />
            </template>
            <n-thing
              title="定时拉盘范围"
              :description="
                loading
                  ? '加载中…'
                  : `已勾选 ${selectedCount} 项。勾选进侧栏「热门」并定时拉盘；未勾选进「其他」，只入库赛程。`
              "
            />
          </n-list-item>
        </n-list>
      </n-card>

      <n-card size="small" title="拉盘联赛" :bordered="false">
        <template #header-extra>
          <n-flex :size="8">
            <n-button size="small" secondary :disabled="loading || saving" @click="restoreDefault">
              恢复默认
            </n-button>
            <n-button
              size="small"
              type="primary"
              :disabled="loading"
              :loading="saving"
              @click="save"
            >
              保存
            </n-button>
          </n-flex>
        </template>
        <n-spin :show="loading">
          <n-checkbox-group v-model:value="selectedIds">
            <div class="hot-league-groups">
              <section v-for="group in leagueGroups" :key="group.title" class="hot-league-group">
                <h3 class="hot-league-group-title">
                  {{ group.title }}
                  <span class="hot-league-group-count">{{ group.selected }}/{{ group.items.length }}</span>
                </h3>
                <div class="hot-league-grid">
                  <n-checkbox
                    v-for="item in group.items"
                    :key="item.league_id"
                    :value="item.league_id"
                    :label="item.league_name"
                  />
                </div>
              </section>
            </div>
          </n-checkbox-group>
          <n-empty
            v-if="!loading && !leagues.length"
            description="目录为空"
            style="padding: 16px 0;"
          />
        </n-spin>
      </n-card>
    </n-flex>
  </MineSectionBody>
</template>

<style scoped>
.hot-league-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hot-league-group-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  opacity: 0.85;
}

.hot-league-group-count {
  margin-left: 8px;
  font-weight: 400;
  opacity: 0.65;
}

.hot-league-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px 12px;
}

@media (min-width: 768px) {
  .hot-league-grid {
    grid-template-columns: repeat(8, minmax(0, 1fr));
  }
}

.hot-league-grid :deep(.n-checkbox) {
  min-width: 0;
}

.hot-league-grid :deep(.n-checkbox__label) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
