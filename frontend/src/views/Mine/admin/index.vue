<script setup lang="ts">
import {
  FlashOutline,
  KeyOutline,
  RefreshOutline,
  SettingsOutline,
  TrashOutline,
} from '@vicons/ionicons5'
import { useMessage, useModal } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'

import {
  fetchApiSportsKeySetting,
  fetchFreeQuotaSetting,
  fetchScheduledFullDetailSetting,
  previewResetMatchHistory,
  resetMatchHistory,
  type ApiSportsKeySetting,
  type ResetMatchHistoryReport,
  updateApiSportsKeySetting,
  updateFreeQuotaSetting,
  updateScheduledFullDetailSetting,
} from '@/api/admin'
import { useAdminSync } from '@/views/Mine/admin/useAdminSync'
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineAdmin' })

const message = useMessage()
const modal = useModal()
const { syncing, statusText, runSync } = useAdminSync()

const enabled = ref(false)
const source = ref('')
const detailBudget = ref(10)
const loading = ref(false)
const saving = ref(false)

const freeQuotaEnabled = ref(true)
const freeQuotaSource = ref('')
const freeQuotaHours = ref<number[]>([11, 22])
const freeQuotaLoading = ref(false)
const freeQuotaSaving = ref(false)

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

function formatSyncHours(hours: number[]): string {
  if (!hours.length) return '—'
  return hours.map((h) => `${String(h).padStart(2, '0')}:00`).join('、')
}

async function loadSetting() {
  loading.value = true
  freeQuotaLoading.value = true
  apiKeyLoading.value = true
  try {
    const [detail, freeQuota, apiKey] = await Promise.all([
      fetchScheduledFullDetailSetting(),
      fetchFreeQuotaSetting(),
      fetchApiSportsKeySetting(),
    ])
    enabled.value = detail.enabled
    source.value = detail.source
    detailBudget.value = Number(detail.budget) || 10
    freeQuotaEnabled.value = freeQuota.enabled
    freeQuotaSource.value = freeQuota.source
    freeQuotaHours.value = freeQuota.sync_hours?.length ? freeQuota.sync_hours : [11, 22]
    apiKeySetting.value = apiKey
  } catch (err) {
    message.error(err instanceof Error ? err.message : '读取管理员设置失败')
  } finally {
    loading.value = false
    freeQuotaLoading.value = false
    apiKeyLoading.value = false
  }
}

async function applyToggle(next: boolean) {
  saving.value = true
  const previous = enabled.value
  enabled.value = next
  try {
    const data = await updateScheduledFullDetailSetting(next)
    enabled.value = data.enabled
    source.value = data.source
    detailBudget.value = Number(data.budget) || detailBudget.value
    if (next) {
      message.success(
        '已开启并写入设置。下次定时同步或点「立即同步」时才会开始预拉详情',
      )
    } else {
      message.success('已关闭定时全量详情')
    }
  } catch (err) {
    enabled.value = previous
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    saving.value = false
  }
}

function onToggle(next: boolean) {
  if (!next) {
    void applyToggle(false)
    return
  }
  modal.create({
    preset: 'dialog',
    title: '确认开启定时全量详情？',
    autoFocus: false,
    type: 'warning',
    content: `开启后不会立刻拉官方接口。会在下一次定时批次，或你点「立即同步」时，为热门联赛未开赛且缺展示包的场次预拉详情（每批最多 ${detailBudget.value} 场），会额外消耗官方 API 配额；配额耗尽会提前停止。确定开启？`,
    positiveText: '确认开启',
    negativeText: '取消',
    onPositiveClick: () => {
      void applyToggle(true)
    },
  })
}

async function applyFreeQuotaToggle(next: boolean) {
  freeQuotaSaving.value = true
  const previous = freeQuotaEnabled.value
  freeQuotaEnabled.value = next
  try {
    const data = await updateFreeQuotaSetting(next)
    freeQuotaEnabled.value = data.enabled
    freeQuotaSource.value = data.source
    freeQuotaHours.value = data.sync_hours?.length
      ? data.sync_hours
      : next
        ? [11, 22]
        : [0, 6, 11, 16, 19, 22]
    if (next) {
      if (data.catch_up_started) {
        message.success(
          '已开启免费配额模式：详情改为完全只读本地，盘口仅由定时批次获取。今日 11:00 已过，正在后台补跑一次同步',
        )
      } else {
        message.success(
          `已开启免费配额模式：详情完全只读本地，盘口仅由定时批次获取。下次自动同步：${formatSyncHours(freeQuotaHours.value)}`,
        )
      }
    } else {
      message.success(
        `已关闭免费配额模式。定时同步恢复为：${formatSyncHours(freeQuotaHours.value)}`,
      )
    }
  } catch (err) {
    freeQuotaEnabled.value = previous
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    freeQuotaSaving.value = false
  }
}

function onFreeQuotaToggle(next: boolean) {
  if (!next) {
    modal.create({
      preset: 'dialog',
      title: '确认关闭免费配额模式？',
      autoFocus: false,
      type: 'warning',
      content:
        '关闭后将恢复每天 00:00、06:00、11:00、16:00、19:00、22:00 共 6 次官方同步，并恢复热门联赛详情的全量按需获取，配额消耗会明显增加。确定关闭？',
      positiveText: '确认关闭',
      negativeText: '取消',
      onPositiveClick: () => {
        void applyFreeQuotaToggle(false)
      },
    })
    return
  }
  modal.create({
    preset: 'dialog',
    title: '确认开启免费配额模式？',
    autoFocus: false,
    type: 'warning',
    content:
      '免费配额模式：开启后立刻重排定时任务，每日 11:00 同步昨天赛果与今天比赛/热门盘口，22:00 再轻量刷新盘口并重算每日推荐；所有详情点击完全只读本地，不补盘口或其它详情，定时全量详情也暂停；跳过积分榜、不拉未来比赛。若今日 11:00 已过会立即补跑一次。确定开启？',
    positiveText: '确认开启',
    negativeText: '取消',
    onPositiveClick: () => {
      void applyFreeQuotaToggle(true)
    },
  })
}

function syncOfficialData() {
  void runSync()
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
  void loadSetting()
})
</script>

<template>
  <MineSectionBody>
    <n-card size="small" title="管理员运维" :bordered="false">
      <n-list>
        <n-list-item>
          <template #prefix>
            <n-icon :component="RefreshOutline" :size="20" />
          </template>
          <n-thing
            title="同步官方 API 数据"
            :description="
              statusText ||
              '立即执行同步；免费配额模式下只拉昨天赛果与今天赛程/盘口，跳过积分榜、不拉未来比赛'
            "
          />
          <template #suffix>
            <n-button
              size="small"
              type="primary"
              :disabled="syncing"
              :loading="syncing"
              @click="syncOfficialData"
            >
              {{ syncing ? '同步中' : '立即同步' }}
            </n-button>
          </template>
        </n-list-item>

        <n-list-item>
          <template #prefix>
            <n-icon :component="FlashOutline" :size="20" />
          </template>
          <n-thing
            title="打开免费配额"
            :description="
              freeQuotaSource
                ? `免费配额模式（每日 11:00 全量 + 22:00 热门盘口；详情完全只读本地，不拉未来）。当前来源：${
                    freeQuotaSource === 'db' ? '管理员覆盖（库）' : '环境变量默认'
                  }；生效整点：${formatSyncHours(freeQuotaHours)}`
                : '免费配额模式（每日 11:00 全量 + 22:00 热门盘口；详情完全只读本地，不拉未来）；默认开启'
            "
          />
          <template #suffix>
            <n-switch
              :value="freeQuotaEnabled"
              :disabled="freeQuotaLoading || freeQuotaSaving"
              :loading="freeQuotaSaving"
              aria-label="打开免费配额"
              @update:value="onFreeQuotaToggle"
            />
          </template>
        </n-list-item>

        <n-list-item>
          <template #prefix>
            <n-icon :component="SettingsOutline" :size="20" />
          </template>
          <n-thing
            title="定时全量获取详情"
            :description="
              freeQuotaEnabled
                ? `免费配额开启中，定时详情暂停；关闭免费配额后恢复此设置（每批最多 ${detailBudget} 场）`
                : source
                ? `当前来源：${source === 'db' ? '管理员覆盖（库）' : '环境变量默认'}；开关只改设置，真正预拉发生在下一次定时批次或「立即同步」（热门联赛未开赛缺包，每批最多 ${detailBudget} 场）`
                : '读取并切换；默认关闭。开启会额外消耗官方 API 配额'
            "
          />
          <template #suffix>
            <n-switch
              :value="enabled"
              :disabled="loading || saving || freeQuotaEnabled"
              :loading="saving"
              aria-label="定时全量获取详情"
              @update:value="onToggle"
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
