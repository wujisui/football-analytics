<script setup lang="ts">
import {
  FlashOutline,
  KeyOutline,
  RefreshOutline,
  SettingsOutline,
  TrashOutline,
  TrophyOutline,
} from '@vicons/ionicons5'
import { useMessage, useModal } from 'naive-ui'
import { computed, onMounted, ref, watch } from 'vue'

import {
  fetchApiSportsKeySetting,
  fetchSubscriptionSetting,
  previewResetMatchHistory,
  resetMatchHistory,
  type ApiSportsKeySetting,
  type LastSyncRun,
  type ResetMatchHistoryReport,
  updateApiSportsKeySetting,
  updateSubscriptionEarlyOdds,
  updateSubscriptionSetting,
} from '@/api/admin'
import TextSwitch from '@/components/TextSwitch.vue'
import { formatLocalDateMinute } from '@/utils/format'
import { useAdminSync } from '@/views/Mine/admin/useAdminSync'
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineAdmin' })

const message = useMessage()
const modal = useModal()
const { syncing, resultsSyncing, busy, runSync, runResultsSync, hydrateStatus } =
  useAdminSync()

const subscribed = ref(false)
const subscriptionSource = ref('')
const earlyOddsEnabled = ref(true)
const fullSyncCompletedToday = ref(false)
const apiRemaining = ref<number | null>(null)
const lastSync = ref<LastSyncRun | null>(null)
const subscriptionLoading = ref(false)
const subscriptionSaving = ref(false)
const earlyOddsSaving = ref(false)

const resetPreview = ref<ResetMatchHistoryReport | null>(null)
const resetPreviewLoading = ref(false)
const resetModalShow = ref(false)
const resetPassword = ref('')
const resetSubmitting = ref(false)

const apiKeySetting = ref<ApiSportsKeySetting | null>(null)
const apiKeyLoading = ref(false)
const apiKeyModalShow = ref(false)
const apiKeyDraft = ref('')
const apiKeyPassword = ref('')
const apiKeySaving = ref(false)

const resetSummary = computed(() => {
  const report = resetPreview.value
  if (!report) return ''
  return [
    `比赛 ${report.fixtures}`,
    `赛前包 ${report.pre_match_data}`,
    `特征 ${report.match_features}`,
    `日推 ${report.auto_pick_snapshots}`,
    `关注 ${report.favorite_fixtures}`,
    `快照 ${report.api_snapshots}`,
    `模型文件 ${report.model_files_removed}`,
  ].join(' · ')
})

const apiKeyDescription = computed(() => {
  const setting = apiKeySetting.value
  if (!setting) return '加载中…'
  return setting.key_count > 0 ? `已配置 ${setting.key_count} 枚 Key` : '未配置'
})

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

/** 上次同步时刻由后端持久化，重启或换浏览器后仍能看到。 */
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
  if (subscribed.value) {
    return `${prefix}已订阅按 Pro 日配额 ≥7500 设计。11:00 每日唯一完整批次；11:55、00/02/14/16/18/20/22 只刷新今天未开赛热门盘口并重算日推。赛程保留 8 天滑动窗口，每天只新增末端一天；盘口与详情只处理今天、明天。`
  }
  return `${prefix}未订阅每天 08:05 只拉当天赛程，11:00 跑昨天赛果与今天赛程/热门盘口，22:00 只刷新今天未开赛热门盘口并重算日推；跳过积分榜与详情预拉，打开详情只读本地。`
})

const earlyOddsDescription = computed(() =>
  subscribed.value
    ? '控制 04:00、06:00、08:00、10:00 是否也刷新今天未开赛热门盘口并重算日推；00:00、02:00 不受此开关影响。'
    : '仅已订阅时生效。',
)

function applySubscription(data: Awaited<ReturnType<typeof fetchSubscriptionSetting>>) {
  subscribed.value = data.subscribed
  subscriptionSource.value = data.source
  earlyOddsEnabled.value = data.early_odds_enabled
  fullSyncCompletedToday.value = data.full_sync_completed_today
  apiRemaining.value = data.api_remaining
  lastSync.value = data.last_sync
}

async function loadSetting() {
  subscriptionLoading.value = true
  apiKeyLoading.value = true
  try {
    const [subscription, apiKey] = await Promise.all([
      fetchSubscriptionSetting(),
      fetchApiSportsKeySetting(),
    ])
    applySubscription(subscription)
    apiKeySetting.value = apiKey
  } catch (err) {
    message.error(err instanceof Error ? err.message : '读取管理员设置失败')
  } finally {
    subscriptionLoading.value = false
    apiKeyLoading.value = false
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

function openApiKeyModal() {
  apiKeyDraft.value = ''
  apiKeyPassword.value = ''
  apiKeyModalShow.value = true
}

function closeApiKeyModal() {
  if (apiKeySaving.value) return
  apiKeyModalShow.value = false
  apiKeyDraft.value = ''
  apiKeyPassword.value = ''
}

async function saveApiSportsKeys() {
  const password = apiKeyPassword.value.trim()
  if (!password) {
    message.warning('请输入管理员登录密码')
    return
  }
  apiKeySaving.value = true
  try {
    apiKeySetting.value = await updateApiSportsKeySetting({
      password,
      keys: apiKeyDraft.value.trim(),
    })
    apiKeyModalShow.value = false
    apiKeyDraft.value = ''
    apiKeyPassword.value = ''
    message.success(
      apiKeySetting.value.key_count > 0
        ? `已保存 ${apiKeySetting.value.key_count} 枚 Key`
        : '已清除全部 Key，官方同步将暂停',
    )
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    apiKeySaving.value = false
  }
}

async function clearApiSportsKeysOverride() {
  const password = apiKeyPassword.value.trim()
  if (!password) {
    message.warning('清除覆盖也需输入管理员登录密码')
    return
  }
  apiKeyDraft.value = ''
  await saveApiSportsKeys()
}

async function openResetModal() {
  resetPassword.value = ''
  resetModalShow.value = true
  resetPreviewLoading.value = true
  resetPreview.value = null
  try {
    resetPreview.value = await previewResetMatchHistory()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '读取清空预览失败')
    resetModalShow.value = false
  } finally {
    resetPreviewLoading.value = false
  }
}

function closeResetModal() {
  if (resetSubmitting.value) return
  resetModalShow.value = false
  resetPassword.value = ''
}

async function confirmResetMatchHistory() {
  const password = resetPassword.value.trim()
  if (!password) {
    message.warning('请输入管理员登录密码')
    return
  }
  resetSubmitting.value = true
  try {
    const report = await resetMatchHistory({ password, apply: true })
    resetPreview.value = report
    resetModalShow.value = false
    resetPassword.value = ''
    await loadSetting()
    message.success(
      `已清空比赛历史（比赛 ${report.fixtures} / 特征 ${report.match_features}）。请再点「立即同步」拉新盘口。`,
    )
  } catch (err) {
    message.error(err instanceof Error ? err.message : '清空失败')
  } finally {
    resetSubmitting.value = false
  }
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
    <n-card size="small" title="管理员运维" :bordered="false">
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
          <n-thing
            title="订阅"
            :description="subscriptionDescription"
          />
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
          <n-thing
            title="早间盘口刷新"
            :description="earlyOddsDescription"
          />
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

        <n-list-item>
          <template #prefix>
            <n-icon :component="KeyOutline" :size="20" />
          </template>
          <n-thing title="API-Sports 官方 Key" :description="apiKeyDescription" />
          <template #suffix>
            <n-button
              size="small"
              secondary
              :disabled="apiKeyLoading || apiKeySaving"
              :loading="apiKeyLoading"
              @click="openApiKeyModal"
            >
              配置
            </n-button>
          </template>
        </n-list-item>

        <n-list-item>
          <template #prefix>
            <n-icon :component="TrashOutline" :size="20" />
          </template>
          <n-thing
            title="清空比赛历史（ML 从零）"
            description="删除赛程/盘口/特征/日推与本地模型文件，保留账号与联赛球队目录；换盘口后重新攒样本用。需输入管理员登录密码确认。"
          />
          <template #suffix>
            <n-button
              size="small"
              type="error"
              secondary
              :disabled="syncing || resetSubmitting"
              @click="openResetModal"
            >
              一键清空
            </n-button>
          </template>
        </n-list-item>
      </n-list>
    </n-card>

    <n-modal
      v-model:show="apiKeyModalShow"
      preset="card"
      title="配置 API-Sports Key"
      :mask-closable="!apiKeySaving"
      :close-on-esc="!apiKeySaving"
      style="width: min(480px, 92vw)"
      @update:show="(show: boolean) => !show && closeApiKeyModal()"
    >
      <n-alert type="info" :bordered="false" style="margin-bottom: 12px">
        多个 Key 用英文逗号分隔；当前 Key 当天配额耗尽后，会自动切换下一枚。
      </n-alert>
      <p
        v-if="apiKeySetting"
        style="margin: 0 0 12px; font-size: 13px; line-height: 1.5; opacity: 0.85"
      >
        当前：{{ apiKeyDescription }}<span v-if="apiKeySetting.masked_keys"
          >；末 4 位：{{ apiKeySetting.masked_keys }}</span
        >
      </p>
      <n-form-item label="官方 Key（可逗号分隔多枚）" :show-feedback="false">
        <n-input
          v-model:value="apiKeyDraft"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 4 }"
          placeholder="key_one,key_two"
          :disabled="apiKeySaving"
        />
      </n-form-item>
      <n-form-item label="管理员登录密码" :show-feedback="false" style="margin-top: 8px">
        <n-input
          v-model:value="apiKeyPassword"
          type="password"
          show-password-on="click"
          placeholder="当前登录管理员的密码"
          autocomplete="current-password"
          :disabled="apiKeySaving"
          @keyup.enter="saveApiSportsKeys"
        />
      </n-form-item>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap">
          <n-button :disabled="apiKeySaving" @click="closeApiKeyModal">取消</n-button>
          <n-button
            secondary
            :disabled="apiKeySaving || !apiKeyPassword.trim()"
            :loading="apiKeySaving"
            @click="clearApiSportsKeysOverride"
          >
            清除全部 Key
          </n-button>
          <n-button
            type="primary"
            :disabled="apiKeySaving || !apiKeyPassword.trim() || !apiKeyDraft.trim()"
            :loading="apiKeySaving"
            @click="saveApiSportsKeys"
          >
            保存
          </n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="resetModalShow"
      preset="card"
      title="确认清空比赛历史？"
      :mask-closable="!resetSubmitting"
      :close-on-esc="!resetSubmitting"
      style="width: min(440px, 92vw)"
      @update:show="(show: boolean) => !show && closeResetModal()"
    >
      <n-spin :show="resetPreviewLoading">
        <n-alert type="warning" :bordered="false" style="margin-bottom: 12px">
          不可恢复。关注列表会一并删除；账号、过关方案、联赛/球队目录会保留。
        </n-alert>
        <p v-if="resetSummary" style="margin: 0 0 12px; font-size: 13px; line-height: 1.5">
          将删除：{{ resetSummary }}
        </p>
        <n-form-item label="管理员登录密码" :show-feedback="false">
          <n-input
            v-model:value="resetPassword"
            type="password"
            show-password-on="click"
            placeholder="当前登录管理员的密码"
            autocomplete="current-password"
            :disabled="resetSubmitting"
            @keyup.enter="confirmResetMatchHistory"
          />
        </n-form-item>
      </n-spin>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <n-button :disabled="resetSubmitting" @click="closeResetModal">取消</n-button>
          <n-button
            type="error"
            :loading="resetSubmitting"
            :disabled="resetPreviewLoading || !resetPassword.trim()"
            @click="confirmResetMatchHistory"
          >
            确认清空
          </n-button>
        </div>
      </template>
    </n-modal>
  </MineSectionBody>
</template>
