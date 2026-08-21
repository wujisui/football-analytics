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
const source = ref('')
const leagues = ref<HotLeagueItem[]>([])
const selectedIds = ref<number[]>([])
const defaultIds = ref<number[]>([])

const selectedCount = computed(() => selectedIds.value.length)
const catalogCount = computed(() => leagues.value.length)
const sourceLabel = computed(() => {
  if (source.value === 'db') return '管理员覆盖（库）'
  if (source.value === 'env') return '内置默认勾选'
  return source.value || '—'
})

function applySetting(data: Awaited<ReturnType<typeof fetchHotLeaguesSetting>>) {
  leagues.value = data.leagues
  selectedIds.value = [...data.league_ids]
  defaultIds.value = [...data.default_league_ids]
  source.value = data.source
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
                  : `目录来自 leagues.json（${catalogCount} 项），勾选后进侧栏「热门」并由定时任务拉赛前盘口；未勾选进「其他」，仍入库赛程但不打官方盘口。当前来源：${sourceLabel}；已勾选 ${selectedCount} 项。`
              "
            />
          </n-list-item>
        </n-list>
      </n-card>

      <n-card size="small" title="勾选" :bordered="false">
        <n-spin :show="loading">
          <n-checkbox-group v-model:value="selectedIds">
            <div class="hot-league-grid">
              <n-checkbox
                v-for="item in leagues"
                :key="item.league_id"
                :value="item.league_id"
                :label="item.league_name"
              />
            </div>
          </n-checkbox-group>
          <n-empty
            v-if="!loading && !leagues.length"
            description="目录为空"
            style="padding: 16px 0;"
          />
        </n-spin>
        <n-flex justify="end" :size="8" style="margin-top: 16px;">
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
      </n-card>
    </n-flex>
  </MineSectionBody>
</template>

<style scoped>
.hot-league-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
}

@media (min-width: 768px) {
  .hot-league-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
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
