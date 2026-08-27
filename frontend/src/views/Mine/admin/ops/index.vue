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
  peekSubscriptionSetting,
  updateSubscriptionDenseOdds,
  updateSubscriptionEarlyOdds,
  updateSubscriptionSetting,
} from '@/api/admin'
import HelpTip from '@/components/HelpTip.vue'
import TextSwitch from '@/components/TextSwitch.vue'
import { useHomeFixtures } from '@/composables/useHomeFixtures'
import { useTrackedLeagues } from '@/composables/useTrackedLeagues'
import { formatLocalDateMinute } from '@/utils/format'
import { prematchFetchParams } from '@/utils/homeDateStrip'
import { useAdminSync } from '@/views/Mine/admin/useAdminSync'
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineAdminOps' })

const message = useMessage()
const modal = useModal()
const {
  syncing,
  resultsSyncing,
  prematchOddsSyncing,
  busy,
  runSync,
  runResultsSync,
  runPrematchOddsSync,
  hydrateStatus,
} = useAdminSync()
const { allFixtures, loadHomeFixtures } = useHomeFixtures()
const { trackedIds, loadFilterOptions } = useTrackedLeagues()
const prematchFixtureIds = computed(() => {
  const selected = new Set(trackedIds.value)
  return allFixtures.value
    .filter((fixture) => selected.has(fixture.league_id))
    .map((fixture) => fixture.fixture_id)
})

const cachedSubscription = peekSubscriptionSetting()
const subscribed = ref(cachedSubscription?.subscribed ?? false)
const subscriptionSource = ref(cachedSubscription?.source ?? '')
const earlyOddsEnabled = ref(cachedSubscription?.early_odds_enabled ?? true)
const denseOddsEnabled = ref(cachedSubscription?.dense_odds_enabled ?? false)
const syncTimes = ref<string[]>(cachedSubscription?.sync_times ?? [])
const apiRemaining = ref<number | null>(cachedSubscription?.api_remaining ?? null)
const lastSync = ref<LastSyncRun | null>(cachedSubscription?.last_sync ?? null)
const subscriptionLoading = ref(cachedSubscription == null)
const subscriptionSaving = ref(false)
const earlyOddsSaving = ref(false)
const denseOddsSaving = ref(false)

const settingSourceLabel = (value: string) =>
  value === 'db' ? '管理员覆盖（库）' : value ? '环境变量默认' : ''

const syncSummary = computed(() =>
  subscribed.value ? '手动同步最新赛程、赛果、盘口与分析数据。' : '订阅关闭时不可用。',
)
const syncDetail = computed(() =>
  subscribed.value
    ? '每次都会回写近 4 天赛果、增量补齐 8 天赛程窗口、更新今天/明天热门盘口与详情、积分榜、训练、日推及清理。不限每日次数，但每次都会消耗官方配额；新增热门联赛后可在这里重新同步。'
    : '完整同步只在已订阅时开放；未订阅仍按 08:05、11:00、22:00 固定任务运行。',
)

const resultsSyncSummary = computed(() =>
  subscribed.value
    ? '只回写近 4 天终场比分，不动盘口与赛程。'
    : '只回写昨天和今天的终场比分，不动盘口与赛程。',
)
const resultsSyncDetail = computed(() =>
  subscribed.value
    ? '只按日回写近 4 天（含今天）的终场比分与训练标签，不拉盘口、赛程或详情。当天「立即同步」完成后仍可用。早间盘口刷新只动未开赛盘口，关了也不会挡住赛果。与完整批次共用官方请求锁，不能同时跑。'
    : '只按日回写昨天和今天的终场比分与训练标签，不拉盘口、赛程或详情。当天「立即同步」完成后仍可用。未订阅的 22:00 轻刷也不回写比分，所以下午完场要靠这一下。与完整批次共用官方请求锁，不能同时跑。',
)

const prematchOddsSummary = computed(() =>
  prematchFixtureIds.value.length
    ? `更新【比赛】当前筛选的 ${prematchFixtureIds.value.length} 场盘口。`
    : '请先进入【比赛】并勾选要显示的联赛。',
)
const prematchOddsDetail =
  '只处理【比赛】当前筛选已勾选联赛对应的未开赛场次；未勾选的“其他”赛事不会进入名单。已有盘口更新即时盘，没有盘口的场次补齐；不拉赛程、赛果、积分榜或详情。每场通常消耗一次官方盘口请求，尚未开盘的比赛仍可能为空。'

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

const subscriptionSummary = computed(() => {
  const source = settingSourceLabel(subscriptionSource.value)
  const suffix = source ? ` · 来源：${source}` : ''
  const count = syncTimes.value.length
  const scale = count ? `每天 ${count} 个定时任务` : '定时任务待读取'
  const head = subscribed.value
    ? `按 Pro 配额调度，${scale}`
    : '每天只跑 08:05、11:00、22:00'
  return `${head}${suffix}`
})
const subscriptionDetail = computed(() => {
  const clocks = syncTimes.value.length
    ? `时刻 ${syncTimes.value.join('、')}。`
    : ''
  if (subscribed.value) {
    return `${clocks}11:00 为每日定时完整批次，其余时刻只刷新今天未开赛热门盘口并重算日推。管理员可不限每日次数手动完整同步；赛程保留 8 天滑动窗口，每天只新增末端一天，盘口与详情只处理今天、明天。`
  }
  return `${clocks}未订阅每天 08:05 只拉当天赛程，11:00 跑昨天赛果与今天赛程/热门盘口，22:00 只刷新今天未开赛热门盘口并重算日推；跳过积分榜与详情预拉，打开详情只读本地。晚间密刷仅已订阅生效。`
})

const earlyOddsSummary = computed(() =>
  subscribed.value ? '04/06/08/10 是否也轻刷盘口。' : '仅已订阅时生效。',
)
const earlyOddsDetail =
  '控制 04:00、06:00、08:00、10:00 是否也刷新今天未开赛热门盘口并重算日推；这四个时刻会叠加到下面选中的方案上，02:00 与晚间时刻不受此开关影响。'

const denseOddsSummary = computed(() => {
  if (!subscribed.value) return '仅已订阅时生效。'
  return denseOddsEnabled.value
    ? '密刷方案：16:55 起每半小时到 01:55。'
    : '默认方案：21:00 起每半小时到 00:00。'
})
const denseOddsDetail =
  '密刷方案：02:00、11:55、14:00、16:00、16:55、17:25、17:55、18:25、18:55、19:25、19:55、20:25、20:55、21:25、21:55、22:25、22:55、23:25、23:55、00:25、00:55、01:25、01:55（开赛整点/半点前 5 分钟）。早间开关的四个时刻叠加到任一方案。'

function applySubscription(data: Awaited<ReturnType<typeof fetchSubscriptionSetting>>) {
  subscribed.value = data.subscribed
  subscriptionSource.value = data.source
  earlyOddsEnabled.value = data.early_odds_enabled
  denseOddsEnabled.value = data.dense_odds_enabled
  syncTimes.value = data.sync_times
  apiRemaining.value = data.api_remaining
  lastSync.value = data.last_sync
}

async function loadSetting(force = false) {
  subscriptionLoading.value = true
  try {
    applySubscription(await fetchSubscriptionSetting(force))
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

function confirmAdminSwitch(title: string, content: string, onConfirm: () => void) {
  modal.create({
    preset: 'dialog',
    title,
    autoFocus: false,
    type: 'warning',
    content,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: onConfirm,
  })
}

function onSubscriptionToggle(next: boolean) {
  confirmAdminSwitch(
    next ? '确认设为已订阅？' : '确认设为未订阅？',
    next
      ? '已订阅按至少 Pro、每日配额 7500 设计；会启用 8 天增量赛程、积分榜、今天/明天热门详情及高频盘口任务。开关本身不会立即同步。'
      : '未订阅将只保留 08:05、11:00、22:00 三个任务，跳过未来赛程、积分榜及详情官方请求。开关本身不会立即同步。',
    () => void applySubscriptionToggle(next),
  )
}

function onEarlyOddsToggle(next: boolean) {
  confirmAdminSwitch(
    next ? '确认开启早间盘口刷新？' : '确认关闭早间盘口刷新？',
    next
      ? '将叠加 04:00、06:00、08:00、10:00 四次盘口轻刷。开关改完立刻重注册定时任务，不会马上打官方。'
      : '04:00、06:00、08:00、10:00 将不再轻刷。开关改完立刻重注册定时任务，不会马上打官方。',
    () => void applyEarlyOddsToggle(next),
  )
}

function onDenseOddsToggle(next: boolean) {
  confirmAdminSwitch(
    next ? '确认切换到密刷方案？' : '确认切回默认方案？',
    next
      ? '将使用完整密刷时刻表（16:55 起每半小时到 01:55）。开关改完立刻重注册定时任务，不会马上打官方。'
      : '将使用完整默认时刻表（21:00 起每半小时到 00:00）。开关改完立刻重注册定时任务，不会马上打官方。',
    () => void applyDenseOddsToggle(next),
  )
}

async function applyDenseOddsToggle(next: boolean) {
  denseOddsSaving.value = true
  const previous = denseOddsEnabled.value
  denseOddsEnabled.value = next
  try {
    applySubscription(await updateSubscriptionDenseOdds(next))
    message.success(next ? '已开启晚间密刷' : '已关闭晚间密刷，恢复默认调度')
  } catch (err) {
    denseOddsEnabled.value = previous
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    denseOddsSaving.value = false
  }
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
}

async function syncResultsOnly() {
  await runResultsSync()
  await loadSetting(true)
}

async function applyPrematchOddsSync() {
  await runPrematchOddsSync(prematchFixtureIds.value)
  await loadSetting(true)
}

function syncPrematchOddsOnly() {
  modal.create({
    preset: 'dialog',
    title: '确认批量更新盘口？',
    type: 'warning',
    content:
      `将逐场更新【比赛】当前筛选的 ${prematchFixtureIds.value.length} 场：已有盘口刷新即时盘，缺盘口则补齐。每场通常消耗一次官方请求。`,
    positiveText: '开始更新',
    negativeText: '取消',
    autoFocus: false,
    onPositiveClick: () => void applyPrematchOddsSync(),
  })
}

async function hydratePrematchOddsList() {
  if (allFixtures.value.length) return
  const { days } = prematchFetchParams()
  try {
    await loadFilterOptions({ days, scope: 'prematch' })
    await loadHomeFixtures({ days, leagueIds: [...trackedIds.value] })
  } catch {
    // The summary remains disabled; the list composables retain their own errors.
  }
}

onMounted(() => {
  void hydrateStatus()
  void hydratePrematchOddsList()
  if (!cachedSubscription) void loadSetting()
})

watch(syncing, (value, previous) => {
  if (previous && !value) void loadSetting(true)
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
          <n-thing :description="syncSummary">
            <template #header>
              <n-flex :size="8" align="center" :wrap="true">
                <span>同步官方 API 数据</span>
                <HelpTip :text="syncDetail" />
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
              :disabled="busy || !subscribed"
              :loading="syncing"
              @click="syncOfficialData"
            >
              {{ syncing ? '同步中' : '立即同步' }}
            </n-button>
          </template>
        </n-list-item>

        <n-list-item>
          <template #prefix>
            <n-icon :component="RefreshOutline" :size="20" />
          </template>
          <n-thing :description="prematchOddsSummary">
            <template #header>
              <n-flex :size="6" align="center">
                <span>批量更新盘口</span>
                <HelpTip :text="prematchOddsDetail" />
              </n-flex>
            </template>
          </n-thing>
          <template #suffix>
            <n-button
              size="small"
              type="primary"
              tertiary
              :disabled="busy || prematchFixtureIds.length === 0"
              :loading="prematchOddsSyncing"
              @click="syncPrematchOddsOnly"
            >
              {{ prematchOddsSyncing ? '更新中' : '批量更新' }}
            </n-button>
          </template>
        </n-list-item>

        <n-list-item>
          <template #prefix>
            <n-icon :component="TrophyOutline" :size="20" />
          </template>
          <n-thing :description="resultsSyncSummary">
            <template #header>
              <n-flex :size="6" align="center">
                <span>只更新赛果</span>
                <HelpTip :text="resultsSyncDetail" />
              </n-flex>
            </template>
          </n-thing>
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
          <n-thing :description="subscriptionSummary">
            <template #header>
              <n-flex :size="6" align="center">
                <span>订阅</span>
                <HelpTip :text="subscriptionDetail" />
              </n-flex>
            </template>
          </n-thing>
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
          <n-thing :description="earlyOddsSummary">
            <template #header>
              <n-flex :size="6" align="center">
                <span>早间盘口刷新</span>
                <HelpTip :text="earlyOddsDetail" />
              </n-flex>
            </template>
          </n-thing>
          <template #suffix>
            <TextSwitch
              :value="earlyOddsEnabled"
              checked-text="已开启"
              unchecked-text="已关闭"
              aria-label="早间盘口刷新"
              :disabled="subscriptionLoading || earlyOddsSaving || !subscribed"
              :loading="earlyOddsSaving"
              @update:value="onEarlyOddsToggle"
            />
          </template>
        </n-list-item>

        <n-list-item>
          <template #prefix>
            <n-icon :component="SettingsOutline" :size="20" />
          </template>
          <n-thing :description="denseOddsSummary">
            <template #header>
              <n-flex :size="6" align="center">
                <span>晚间密刷盘口</span>
                <HelpTip :text="denseOddsDetail" />
              </n-flex>
            </template>
          </n-thing>
          <template #suffix>
            <TextSwitch
              :value="denseOddsEnabled"
              checked-text="已开启"
              unchecked-text="已关闭"
              aria-label="晚间密刷盘口"
              :disabled="subscriptionLoading || denseOddsSaving || !subscribed"
              :loading="denseOddsSaving"
              @update:value="onDenseOddsToggle"
            />
          </template>
        </n-list-item>
      </n-list>
    </n-card>
  </MineSectionBody>
</template>
