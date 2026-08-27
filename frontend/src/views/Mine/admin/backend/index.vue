<script setup lang="ts">
import { KeyOutline, TrashOutline } from '@vicons/ionicons5'
import { useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'

import {
  fetchApiSportsKeySetting,
  peekApiSportsKeySetting,
  previewResetMatchHistory,
  resetMatchHistory,
  type ApiSportsKeySetting,
  type ResetMatchHistoryReport,
  updateApiSportsKeySetting,
} from '@/api/admin'
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineAdminBackend' })

const message = useMessage()

const resetPreview = ref<ResetMatchHistoryReport | null>(null)
const resetPreviewLoading = ref(false)
const resetModalShow = ref(false)
const resetPassword = ref('')
const resetSubmitting = ref(false)

const cachedApiKeySetting = peekApiSportsKeySetting()
const apiKeySetting = ref<ApiSportsKeySetting | null>(cachedApiKeySetting)
const apiKeyLoading = ref(cachedApiKeySetting == null)
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

async function loadApiKeySetting() {
  apiKeyLoading.value = true
  try {
    apiKeySetting.value = await fetchApiSportsKeySetting()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '读取 Key 配置失败')
  } finally {
    apiKeyLoading.value = false
  }
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
      `已清空比赛历史（比赛 ${report.fixtures} / 特征 ${report.match_features}）。请再到「运维」点「立即同步」拉新盘口。`,
    )
  } catch (err) {
    message.error(err instanceof Error ? err.message : '清空失败')
  } finally {
    resetSubmitting.value = false
  }
}

onMounted(() => {
  if (!cachedApiKeySetting) void loadApiKeySetting()
})
</script>

<template>
  <MineSectionBody>
    <n-card size="small" title="后台管理" :bordered="false">
      <n-list>
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
              :disabled="resetSubmitting"
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
