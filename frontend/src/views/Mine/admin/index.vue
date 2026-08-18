<script setup lang="ts">
import { FlashOutline, RefreshOutline, SettingsOutline } from '@vicons/ionicons5'
import { useMessage, useModal } from 'naive-ui'
import { onMounted, ref } from 'vue'

import {
  fetchFreeQuotaSetting,
  fetchScheduledFullDetailSetting,
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

function formatSyncHours(hours: number[]): string {
  if (!hours.length) return '—'
  return hours.map((h) => `${String(h).padStart(2, '0')}:00`).join('、')
}

async function loadSetting() {
  loading.value = true
  freeQuotaLoading.value = true
  try {
    const [detail, freeQuota] = await Promise.all([
      fetchScheduledFullDetailSetting(),
      fetchFreeQuotaSetting(),
    ])
    enabled.value = detail.enabled
    source.value = detail.source
    detailBudget.value = Number(detail.budget) || 10
    freeQuotaEnabled.value = freeQuota.enabled
    freeQuotaSource.value = freeQuota.source
    freeQuotaHours.value = freeQuota.sync_hours?.length ? freeQuota.sync_hours : [11, 22]
  } catch (err) {
    message.error(err instanceof Error ? err.message : '读取管理员设置失败')
  } finally {
    loading.value = false
    freeQuotaLoading.value = false
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
    freeQuotaHours.value = data.sync_hours?.length ? data.sync_hours : next ? [11, 22] : [0, 6, 11, 16, 19, 22]
    if (next) {
      if (data.catch_up_started) {
        message.success(
          '已开启免费配额模式（每日 11:00 全量 + 22:00 盘口）。今日 11:00 已过，正在后台补跑一次同步',
        )
      } else {
        message.success(
          `已开启免费配额模式（每日 11:00 全量 + 22:00 盘口）。下次自动同步：${formatSyncHours(freeQuotaHours.value)}`,
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
        '关闭后将恢复每天 00:00、06:00、11:00、16:00、19:00、22:00 共 6 次官方同步，配额消耗会明显增加。确定关闭？',
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
        '免费配额模式：开启后立刻重排定时任务，每日 11:00 同步昨天赛果与今天比赛/盘口，22:00 再轻量刷新今天热门联赛盘口并重算每日推荐；跳过积分榜、不拉未来比赛；若今日 11:00 已过会立即补跑一次。「立即同步」不受时间限制，走 11:00 同款全量范围。确定开启？',
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
                ? `免费配额模式（每日 11:00 全量 + 22:00 盘口，同步昨天赛果 + 今天比赛，不拉未来）。当前来源：${
                    freeQuotaSource === 'db' ? '管理员覆盖（库）' : '环境变量默认'
                  }；生效整点：${formatSyncHours(freeQuotaHours)}`
                : '免费配额模式（每日 11:00 全量 + 22:00 盘口，同步昨天赛果 + 今天比赛，不拉未来）；默认开启'
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
  </MineSectionBody>
</template>
