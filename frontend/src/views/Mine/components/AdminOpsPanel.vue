<script setup lang="ts">
import { RefreshOutline, SettingsOutline } from '@vicons/ionicons5'
import { useMessage, useModal } from 'naive-ui'
import { onMounted, ref } from 'vue'

import {
  fetchScheduledFullDetailSetting,
  updateScheduledFullDetailSetting,
} from '@/api/admin'
import { useAdminSync } from '@/views/Mine/composables/useAdminSync'

defineOptions({ name: 'AdminOpsPanel' })

const message = useMessage()
const modal = useModal()
const { syncing, statusText, runSync } = useAdminSync()

const enabled = ref(false)
const source = ref('')
const detailBudget = ref(10)
const loading = ref(false)
const saving = ref(false)

async function loadSetting() {
  loading.value = true
  try {
    const data = await fetchScheduledFullDetailSetting()
    enabled.value = data.enabled
    source.value = data.source
    detailBudget.value = Number(data.budget) || 10
  } catch (err) {
    message.error(err instanceof Error ? err.message : '读取管理员设置失败')
  } finally {
    loading.value = false
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
  // Opening burns official quota — confirm before persisting.
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
            '立即执行一次赛程、盘口与赛果同步；若下方开关已开，同批会按预算预拉缺包详情'
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
              ? `当前来源：${source === 'db' ? '管理员覆盖（库）' : '环境变量默认'}；开关只改设置，真正预拉发生在下一次定时批次或「立即同步」（热门联赛未开赛缺包，每批最多 ${detailBudget} 场）`
              : '读取并切换；默认关闭。开启会额外消耗官方 API 配额'
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
