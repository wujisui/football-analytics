<script setup lang="ts">
import { RefreshOutline, SettingsOutline } from '@vicons/ionicons5'
import { useMessage } from 'naive-ui'
import { onMounted, ref } from 'vue'

import {
  fetchScheduledFullDetailSetting,
  updateScheduledFullDetailSetting,
} from '@/api/admin'
import { useAdminSync } from '@/views/Mine/composables/useAdminSync'

defineOptions({ name: 'AdminOpsPanel' })

const message = useMessage()
const { syncing, statusText, runSync } = useAdminSync()

const enabled = ref(false)
const source = ref('')
const loading = ref(false)
const saving = ref(false)

async function loadSetting() {
  loading.value = true
  try {
    const data = await fetchScheduledFullDetailSetting()
    enabled.value = data.enabled
    source.value = data.source
  } catch (err) {
    message.error(err instanceof Error ? err.message : '读取管理员设置失败')
  } finally {
    loading.value = false
  }
}

async function onToggle(next: boolean) {
  saving.value = true
  const previous = enabled.value
  enabled.value = next
  try {
    const data = await updateScheduledFullDetailSetting(next)
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
  void runSync()
}

onMounted(() => {
  void loadSetting()
})
</script>

<template>
  <n-card size="small" title="管理员运维" :bordered="false">
    <n-alert type="info" :show-icon="false" style="margin-bottom: 12px">
      当前账号已具备管理员权限。入口仅对
      <code>is_admin</code>
      账号可见。授予：
      <code>python manage.py set-admin &lt;账号&gt;</code>
      ；取消：
      <code>python manage.py unset-admin &lt;账号&gt;</code>
      。
    </n-alert>

    <n-list>
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
          <n-icon :component="SettingsOutline" :size="20" />
        </template>
        <n-thing
          title="定时全量获取详情"
          :description="
            source
              ? `当前来源：${source === 'db' ? '管理员覆盖（库）' : '环境变量默认'}；开启后由定时批次预拉展示包（实现就绪后生效）`
              : '读取并切换；默认关闭，详情仍按点击补拉'
          "
        />
        <template #suffix>
          <n-switch
            :value="enabled"
            :disabled="loading || saving"
            :loading="saving"
            aria-label="定时全量获取详情"
            @update:value="onToggle"
          />
        </template>
      </n-list-item>
    </n-list>
  </n-card>
</template>
