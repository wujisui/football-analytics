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
    .filter(
      (fixture) =>
        (fixture.match_day_offset ?? 0) === 0 &&
        selected.has(fixture.league_id),
    )
    .map((fixture) => fixture.fixture_id)
})

const cachedSubscription = peekSubscriptionSetting()
const subscribed = ref(cachedSubscription?.subscribed ?? false)
const subscriptionSource = ref(cachedSubscription?.source ?? '')
const denseOddsEnabled = ref(cachedSubscription?.dense_odds_enabled ?? false)
const syncTimes = ref<string[]>(cachedSubscription?.sync_times ?? [])
const apiRemaining = ref<number | null>(cachedSubscription?.api_remaining ?? null)
const lastSync = ref<LastSyncRun | null>(cachedSubscription?.last_sync ?? null)
const subscriptionLoading = ref(cachedSubscription == null)
const subscriptionSaving = ref(false)
const denseOddsSaving = ref(false)

const settingSourceLabel = (value: string) =>
  value === 'db' ? '管理员覆盖（库）' : value ? '环境变量默认' : ''

const syncSummary = computed(() =>
  subscribed.value ? '手动同步最新赛程、赛果、盘口与分析数据。' : '订阅关闭时不可用。',
)
const syncDetail = computed(() =>
  subscribed.value
    ? '等同执行一次 10:55 已订阅完整批次：回写昨天和今天赛果、增量补齐 8 天赛程窗口、刷新今天盘口、补齐明天初盘、预拉今天/明天详情，并执行积分榜、训练、日推及清理。不限每日次数，但每次都会消耗官方配额。'
    : '完整同步只在已订阅时开放；未订阅仍按 07:00、08:05、10:55、22:00 固定任务运行。',
)

const resultsSyncSummary = '只回写昨天和今天的终场比分，不动盘口与赛程。'
const resultsSyncDetail =
  '只按日回写调度时区昨天和今天的终场比分与训练标签（例如周六回写周五晚场，下午完场当天就能补上）。不拉前几天，不拉盘口/赛程/详情。每天 07:00 定时与此按钮范围相同。与完整批次共用官方请求锁，不能同时跑。'

const prematchOddsSummary = computed(() =>
  prematchFixtureIds.value.length
    ? `更新【比赛】当前筛选中今天的 ${prematchFixtureIds.value.length} 场热门赛事盘口。`
    : '当前筛选没有今天的热门未开赛赛事。',
)
const prematchOddsDetail =
  '只处理【比赛】当前筛选中比赛日为今天的热门未开赛场次；明天及非热门赛事即使在列表中也排除。后端会再次校验比赛日和热门状态。已有盘口更新即时盘，没有盘口的场次补齐；不拉赛程、赛果、积分榜或详情。每场通常消耗一次官方盘口请求，尚未开盘的比赛仍可能为空。'

const lastSyncText = computed(() => {
  if (syncing.value) return '同步进行中，完成后会全局提示'
  const run = lastSync.value
  if (!run) return '尚无同步记录'
  const when = formatLocalDateMinute(run.finished_at)
  const suffix = run.status === 'failed' ? '失败' : ''
  return `${run.label} · ${suffix} ${when}`
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
    : '每天只跑 07:00、08:05、10:55、22:00'
  return `${head}${suffix}`
})
const subscriptionDetail = computed(() => {
  const clocks = denseOddsEnabled.value
    ? '时刻：07:00 赛果回写、10:55 完整批次；密刷按每小时 25/55 分全天循环。'
    : syncTimes.value.length
      ? `时刻 ${syncTimes.value.join('、')}。`
      : ''
  if (subscribed.value) {
    return `${clocks}07:00 回写昨天和今天赛果；10:55 为每日定时完整批次。赛程保留 8 天滑动窗口且每天只补末端一天；今天盘口刷新为即时盘，明天缺盘补齐并冻结为初盘；详情只预拉今天、明天。关闭密刷后采用 07:00、08:05、10:55、22:00 的稀疏时刻，但 10:55 仍执行已订阅完整批次，立即同步仍可用。`
  }
  return `${clocks}未订阅每天 07:00 回写昨天和今天赛果，08:05 只拉当天赛程，10:55 跑昨天/今天赛果与今天赛程/热门盘口，22:00 只刷新今天未开赛热门盘口并重算日推；跳过积分榜与详情预拉，打开详情只读本地。密刷会随订阅关闭并禁用。`
})

const denseOddsSummary = computed(() => {
  if (!subscribed.value) return '订阅关闭时同步关闭并禁用。'
  return denseOddsEnabled.value
    ? '从 11:25 起每 30 分钟循环刷新，全天不停。'
    : '密刷已关闭，采用未订阅时刻表。'
})
const denseOddsDetail =
  '打开订阅会自动开启密刷。从 11:25 起按每小时 25 分、55 分持续循环 24 小时，只刷新比赛日为今天且仍未开赛的目录盘口并重算日推。10:55 会先执行完整批次，再执行同刻密刷。手动关闭后采用 07:00、08:05、10:55、22:00 时刻表，但仍保留已订阅完整批次和立即同步能力。'

function applySubscription(data: Awaited<ReturnType<typeof fetchSubscriptionSetting>>) {
  subscribed.value = data.subscribed
  subscriptionSource.value = data.source
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
  if (subscriptionSaving.value) return
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
      ? '会自动开启全天密刷，并启用 8 天增量赛程、积分榜、今天即时盘、明天初盘及今天/明天详情。开关本身不会立即同步。'
      : '会同时关闭并禁用密刷，只保留 07:00、08:05、10:55、22:00，跳过未来赛程、积分榜及详情官方请求。开关本身不会立即同步。',
    () => void applySubscriptionToggle(next),
  )
}

function onDenseOddsToggle(next: boolean) {
  confirmAdminSwitch(
    next ? '确认开启密刷？' : '确认关闭密刷？',
    next
      ? '将从 11:25 起每 30 分钟循环刷新全天盘口；10:55 完整批次后还会执行同刻密刷。保存后立刻重排定时任务，但不会马上请求官方。'
      : '将改用 07:00、08:05、10:55、22:00 时刻表；10:55 仍执行已订阅完整批次，立即同步仍可用。',
    () => void applyDenseOddsToggle(next),
  )
}

async function applyDenseOddsToggle(next: boolean) {
  if (denseOddsSaving.value) return
  denseOddsSaving.value = true
  const previous = denseOddsEnabled.value
  denseOddsEnabled.value = next
  try {
    applySubscription(await updateSubscriptionDenseOdds(next))
    message.success(next ? '已开启密刷' : '已关闭密刷，改用稀疏调度')
  } catch (err) {
    denseOddsEnabled.value = previous
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    denseOddsSaving.value = false
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
    title: '确认更新盘口？',
    type: 'warning',
    content:
      `将逐场更新【比赛】当前筛选中今天的 ${prematchFixtureIds.value.length} 场热门赛事：已有盘口刷新即时盘，缺盘口则补齐。每场通常消耗一次官方请求。`,
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
    <n-card size="small" :bordered="false" class="ops-card">
      <template #header>
        <n-text
          depth="3"
          :type="lastSync?.status === 'failed' ? 'error' : undefined"
          class="ops-last-sync"
        >
          {{ lastSyncText }}
        </n-text>
      </template>
      <template #header-extra>
        <n-flex :size="6" align="center" :wrap="false">
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
              <n-flex :size="6" align="center">
                <span>同步数据</span>
                <HelpTip :text="syncDetail" />
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
                <span>更新盘口</span>
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
              {{ prematchOddsSyncing ? '更新中' : '更新' }}
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
                <span>更新赛果</span>
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
                <span>打开订阅</span>
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
          <n-thing :description="denseOddsSummary">
            <template #header>
              <n-flex :size="6" align="center">
                <span>开启密刷</span>
                <HelpTip :text="denseOddsDetail" />
              </n-flex>
            </template>
          </n-thing>
          <template #suffix>
            <TextSwitch
              :value="denseOddsEnabled"
              checked-text="已开启"
              unchecked-text="已关闭"
              aria-label="开启密刷"
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

<style scoped>
.ops-card :deep(.n-card-header) {
  gap: 8px;
}

.ops-card :deep(.n-card-header__main) {
  min-width: 0;
}

.ops-last-sync {
  display: block;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ops-card :deep(.n-card-header__extra) {
  flex-shrink: 0;
}
</style>
