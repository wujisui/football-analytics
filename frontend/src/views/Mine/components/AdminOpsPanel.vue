<script setup lang="ts">
import { KeyOutline, RefreshOutline, SettingsOutline } from '@vicons/ionicons5'
import { useMessage } from 'naive-ui'
import { onMounted, ref, watch } from 'vue'

import {
  fetchScheduledFullDetailSetting,
  updateScheduledFullDetailSetting,
} from '@/api/admin'
import { useAdminSession } from '@/composables/useAdminSession'
import { useAdminSync } from '@/views/Mine/composables/useAdminSync'

defineOptions({ name: 'AdminOpsPanel' })

const message = useMessage()
const { adminKey, hasAdminKey, setAdminKey, clearAdminKey } = useAdminSession()
const { syncing, statusText, runSync } = useAdminSync()

const keyDraft = ref(adminKey.value)
const enabled = ref(false)
const source = ref('')
const loading = ref(false)
const saving = ref(false)

async function loadSetting() {
  if (!adminKey.value) return
  loading.value = true
  try {
    const data = await fetchScheduledFullDetailSetting(adminKey.value)
    enabled.value = data.enabled
    source.value = data.source
  } catch (err) {
    message.error(err instanceof Error ? err.message : '读取管理员设置失败')
  } finally {
    loading.value = false
  }
}

function saveKey() {
  setAdminKey(keyDraft.value)
  if (!adminKey.value) {
    message.warning('请输入管理员密钥')
    return
  }
  void loadSetting()
}

function forgetKey() {
  clearAdminKey()
  keyDraft.value = ''
  enabled.value = false
  source.value = ''
}

async function onToggle(next: boolean) {
  if (!adminKey.value) return
  saving.value = true
  const previous = enabled.value
  enabled.value = next
  try {
    const data = await updateScheduledFullDetailSetting(adminKey.value, next)
    enabled.value = data.enabled
    source.value = data.source
    message.success(next ? '已开启定时全量详情（落库生效）' : '已关闭定时全量详情')
  } catch (err) {
    enabled.value = previous
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    saving.value = false
  }
}

function syncOfficialData() {
  if (!adminKey.value) {
    message.warning('请先验证管理员密钥')
    return
  }
  void runSync(adminKey.value)
}

watch(adminKey, (value) => {
  keyDraft.value = value
})

onMounted(() => {
  if (hasAdminKey.value) void loadSetting()
})
</script>

<template>
  <n-card size="small" title="管理员运维" :bordered="false">
    <n-alert type="warning" :show-icon="false" style="margin-bottom: 12px">
      需后端配置 <code>ADMIN_API_KEY</code>。密钥只保存在本机浏览器，不会写入构建产物。
    </n-alert>

    <n-list>
      <n-list-item>
        <template #prefix>
          <n-icon :component="KeyOutline" :size="20" />
        </template>
        <n-thing title="管理员密钥" description="对应请求头 X-Admin-Key" />
        <template #suffix>
          <div class="admin-key-actions">
            <n-input
              v-model:value="keyDraft"
              type="password"
              show-password-on="click"
              size="small"
              placeholder="ADMIN_API_KEY"
              style="width: min(220px, 42vw)"
              @keyup.enter="saveKey"
            />
            <n-button size="small" type="primary" :loading="loading" @click="saveKey">
              验证
            </n-button>
            <n-button
              v-if="hasAdminKey"
              size="small"
              quaternary
              @click="forgetKey"
            >
              清除
            </n-button>
          </div>
        </template>
      </n-list-item>

      <n-list-item>
        <template #prefix>
          <n-icon :component="RefreshOutline" :size="20" />
        </template>
        <n-thing
          title="同步官方 API 数据"
          :description="
            statusText ||
            '立即执行一次赛程、盘口与赛果同步，开发服务中断后可用来补齐最新数据'
          "
        />
        <template #suffix>
          <n-button
            size="small"
            type="primary"
            :disabled="!hasAdminKey || syncing"
            :loading="syncing"
            @click="syncOfficialData"
          >
            {{ syncing ? '同步中' : '立即同步' }}
          </n-button>
        </template>
      </n-list-item>

      <n-list-item>
        <template #prefix>
          <n-icon :component="SettingsOutline" :size="20" />
        </template>
        <n-thing
          title="定时全量获取详情"
          :description="
            source
              ? `当前来源：${source === 'db' ? '管理员覆盖（库）' : '环境变量默认'}；开启后由定时批次预拉展示包（实现就绪后生效）`
              : '验证密钥后可读取并切换；默认关闭，详情仍按点击补拉'
          "
        />
        <template #suffix>
          <n-switch
            :value="enabled"
            :disabled="!hasAdminKey || loading || saving"
            :loading="saving"
            aria-label="定时全量获取详情"
            @update:value="onToggle"
          />
        </template>
      </n-list-item>
    </n-list>
  </n-card>
</template>

<style scoped>
.admin-key-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
</style>
