<script setup lang="ts">
import {
  FlashOutline,
  RefreshOutline,
  SettingsOutline,
  TrophyOutline,
} from '@vicons/ionicons5'
import { useMessage, useModal } from 'naive-ui'
import { computed, onMounted, ref, watch } from 'vue'

import {
  fetchSubscriptionSetting,
  type LastSyncRun,
  updateSubscriptionEarlyOdds,
  updateSubscriptionSetting,
} from '@/api/admin'
import TextSwitch from '@/components/TextSwitch.vue'
import { formatLocalDateMinute } from '@/utils/format'
import { useAdminSync } from '@/views/Mine/admin/useAdminSync'
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineAdminOps' })

const message = useMessage()
const modal = useModal()
const { syncing, resultsSyncing, busy, runSync, runResultsSync, hydrateStatus } =
  useAdminSync()

const subscribed = ref(false)
const subscriptionSource = ref('')
const earlyOddsEnabled = ref(true)
const syncTimes = ref<string[]>([])
const fullSyncCompletedToday = ref(false)
const apiRemaining = ref<number | null>(null)
const lastSync = ref<LastSyncRun | null>(null)
const subscriptionLoading = ref(false)
const subscriptionSaving = ref(false)
const earlyOddsSaving = ref(false)

const settingSourceLabel = (value: string) =>
  value === 'db' ? '管理员覆盖（库）' : value ? '环境变量默认' : ''

const syncDescription = computed(() =>
  subscribed.value
    ? '当天完整批次尚未成功时可手动补跑：回写近 4 天赛果、增量补齐 8 天赛程窗口、更新今天/明天热门盘口与详情、积分榜、训练、日推及清理；成功后当天禁用，避免重复消耗。完场比分若还要再刷，用下面的「只更新赛果」。'
    : '当天 11:00 完整批次尚未成功时可手动补跑：昨天赛果、今天赛程/热门盘口、训练、日推及清理；成功后当天禁用。08:05 当天赛程是独立任务，不补跑。完场比分若还要再刷，用下面的「只更新赛果」。',
)

const resultsSyncDescription = computed(() =>
  subscribed.value
    ? '只按日回写近 4 天（含今天）的终场比分与训练标签，不拉盘口、赛程或详情。当天「立即同步」完成后仍可用。早间盘口刷新只动未开赛盘口，关了也不会挡住赛果。与完整批次共用官方请求锁，不能同时跑。'
    : '只按日回写昨天和今天的终场比分与训练标签，不拉盘口、赛程或详情。当天「立即同步」完成后仍可用。未订阅的 22:00 轻刷也不回写比分，所以下午完场要靠这一下。与完整批次共用官方请求锁，不能同时跑。',
)

const lastSyncText = computed(() => {
  if (syncing.value) return '同步进行中，完成后会全局提示'
  const run = lastSync.value
  if (!run) return '尚无同步记录'
  const when = formatLocalDateMinute(run.finished_at)
  const suffix = run.status === 'failed' ? '失败' : ''
  return `上次同步${suffix} ${when} · ${run.label}`
})

const lastSyncQuotaText = computed(() => {
  const run = lastSync.value
  return run ? `本次消耗 ${run.quota_used}` : ''
})

const subscriptionDescription = computed(() => {
  const source = settingSourceLabel(subscriptionSource.value)
  const prefix = source ? `当前来源：${source}。` : ''
  const clocks = syncTimes.value.length
    ? `时刻 ${syncTimes.value.join('、')}。`
    : ''
  if (subscribed.value) {
    const early = earlyOddsEnabled.value
      ? '早间盘口刷新已开启（04/06/08/10）。'
      : '早间盘口刷新已关闭，04/06/08/10 不跑。'
    return `${prefix}${clocks}11:00 为每日唯一完整批次，其余时刻只刷新今天未开赛热门盘口并重算日推；21:00 至 24:00 每隔半小时一次。${early}赛程保留 8 天滑动窗口，每天只新增末端一天；盘口与详情只处理今天、明天。`
  }
  return `${prefix}${clocks}未订阅每天 08:05 只拉当天赛程，11:00 跑昨天赛果与今天赛程/热门盘口，22:00 只刷新今天未开赛热门盘口并重算日推；跳过积分榜与详情预拉，打开详情只读本地。晚间半小时刷新仅已订阅生效。`
})

const earlyOddsDescription = computed(() =>
  subscribed.value
    ? '控制 04:00、06:00、08:00、10:00 是否也刷新今天未开赛热门盘口并重算日推；02:00 与 21:00–24:00 的半小时任务不受此开关影响。'
    : '仅已订阅时生效。',
)

function applySubscription(data: Awaited<ReturnType<typeof fetchSubscriptionSetting>>) {
  subscribed.value = data.subscribed
  subscriptionSource.value = data.source
  earlyOddsEnabled.value = data.early_odds_enabled
  syncTimes.value = data.sync_times
  fullSyncCompletedToday.value = data.full_sync_completed_today
  apiRemaining.value = data.api_remaining
  lastSync.value = data.last_sync
}

async function loadSetting() {
  subscriptionLoading.value = true
  try {
    applySubscription(await fetchSubscriptionSetting())
  } catch (err) {
    message.error(err instanceof Error ? err.message : '读取运维设置失败')
  } finally {
    subscriptionLoading.value = false
  }
}

async function applySubscriptionToggle(next: boolean) {
  subscriptionSaving.value = true
  const previous = subscribed.value
  subscribed.value = next
  try {
    applySubscription(await updateSubscriptionSetting(next))
    message.success(next ? '已切换为已订阅' : '已切换为未订阅')
  } catch (err) {
    subscribed.value = previous
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    subscriptionSaving.value = false
  }
}

function onSubscriptionToggle(next: boolean) {
  modal.create({
    preset: 'dialog',
    title: next ? '确认设为已订阅？' : '确认设为未订阅？',
    autoFocus: false,
    type: 'warning',
    content: next
      ? '已订阅按至少 Pro、每日配额 7500 设计；会启用 8 天增量赛程、积分榜、今天/明天热门详情及高频盘口任务。开关本身不会立即同步。'
      : '未订阅将只保留 08:05、11:00、22:00 三个任务，跳过未来赛程、积分榜及详情官方请求。开关本身不会立即同步。',
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: () => void applySubscriptionToggle(next),
  })
}

async function applyEarlyOddsToggle(next: boolean) {
  earlyOddsSaving.value = true
  const previous = earlyOddsEnabled.value
  earlyOddsEnabled.value = next
  try {
    applySubscription(await updateSubscriptionEarlyOdds(next))
    message.success(next ? '已开启早间盘口刷新' : '已关闭早间盘口刷新')
  } catch (err) {
    earlyOddsEnabled.value = previous
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    earlyOddsSaving.value = false
  }
}

async function syncOfficialData() {
  await runSync()
  await loadSetting()
}

async function syncResultsOnly() {
  await runResultsSync()
  await loadSetting()
}

onMounted(() => {
  void hydrateStatus()
  void loadSetting()
})

watch(syncing, (value, previous) => {
  if (previous && !value) void loadSetting()
})
</script>

<template>
  <MineSectionBody>
    <n-card size="small" :bordered="false">
      <template #header>
        <span></span>
      </template>
      <template #header-extra>
        <n-flex :size="6" align="center">
          <n-tag v-if="apiRemaining != null" size="small" :bordered="false" type="info">
            官方剩余 {{ apiRemaining }}
          </n-tag>
          <n-tag v-if="lastSyncQuotaText" size="small" :bordered="false">
            {{ lastSyncQuotaText }}
          </n-tag>
        </n-flex>
      </template>
      <n-list>
        <n-list-item>
          <template #prefix>
            <n-icon :component="RefreshOutline" :size="20" />
          </template>
          <n-thing :description="syncDescription">
            <template #header>
              <n-flex :size="8" align="baseline" :wrap="true">
                <span>同步官方 API 数据</span>
                <n-text
                  depth="3"
                  :type="lastSync?.status === 'failed' ? 'error' : undefined"
                  style="font-size: 12px"
                >
                  {{ lastSyncText }}
                </n-text>
              </n-flex>
            </template>
          </n-thing>
          <template #suffix>
            <n-button
              size="small"
              type="primary"
              :disabled="busy || fullSyncCompletedToday"
              :loading="syncing"
              @click="syncOfficialData"
            >
              {{ syncing ? '同步中' : fullSyncCompletedToday ? '今日已同步' : '立即同步' }}
            </n-button>
          </template>
        </n-list-item>

        <n-list-item>
          <template #prefix>
            <n-icon :component="TrophyOutline" :size="20" />
          </template>
          <n-thing title="只更新赛果" :description="resultsSyncDescription" />
          <template #suffix>
            <n-button
              size="small"
              :disabled="busy"
              :loading="resultsSyncing"
              @click="syncResultsOnly"
            >
              {{ resultsSyncing ? '更新中' : '更新赛果' }}
            </n-button>
          </template>
        </n-list-item>

        <n-list-item>
          <template #prefix>
            <n-icon :component="FlashOutline" :size="20" />
          </template>
          <n-thing title="订阅" :description="subscriptionDescription" />
          <template #suffix>
            <TextSwitch
              :value="subscribed"
              checked-text="已订阅"
              unchecked-text="未订阅"
              aria-label="订阅状态"
              :disabled="subscriptionLoading || subscriptionSaving"
              :loading="subscriptionSaving"
              @update:value="onSubscriptionToggle"
            />
          </template>
        </n-list-item>

        <n-list-item>
          <template #prefix>
            <n-icon :component="SettingsOutline" :size="20" />
          </template>
          <n-thing title="早间盘口刷新" :description="earlyOddsDescription" />
          <template #suffix>
            <TextSwitch
              :value="earlyOddsEnabled"
              checked-text="已开启"
              unchecked-text="已关闭"
              aria-label="早间盘口刷新"
              :disabled="subscriptionLoading || earlyOddsSaving || !subscribed"
              :loading="earlyOddsSaving"
              @update:value="applyEarlyOddsToggle"
            />
          </template>
        </n-list-item>
      </n-list>
    </n-card>
  </MineSectionBody>
</template>
