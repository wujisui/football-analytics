<script setup lang="ts">
import {
  ChevronForwardOutline,
  LogInOutline,
  LogOutOutline,
  PersonOutline,
} from '@vicons/ionicons5'
import { useModal } from 'naive-ui'
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthSession } from '@/composables/useAuthSession'
import { useIsPhone } from '@/composables/useMediaQuery'
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'
import { confirmLogout } from '@/views/Mine/confirmLogout'
import {
  isAdminOnlySection,
  sectionMeta,
  type MineSection,
} from '@/views/Mine/sectionMeta'

defineOptions({ name: 'MineAccount' })

const router = useRouter()
const modal = useModal()
const isPhone = useIsPhone()
const { isLoggedIn, isAdmin, username, openLogin, logout } = useAuthSession()

const profileTitle = computed(() =>
  isLoggedIn.value ? username.value : '未登录',
)
const roleLabel = computed(() => {
  if (!isLoggedIn.value) return '游客'
  return isAdmin.value ? '管理员' : '普通用户'
})
const inactiveVipTagColor = {
  color: 'rgba(128, 128, 128, 0.14)',
  borderColor: 'rgba(128, 128, 128, 0.32)',
  textColor: 'rgba(128, 128, 128, 0.9)',
}

const mobileSections = computed(() => {
  const keys: MineSection[] = ['plans', 'theme']
  if (isAdmin.value) {
    keys.push(
      'adminOps',
      'adminBackend',
      'hotLeagues',
      'vipMembers',
      'vipRecords',
    )
  }
  keys.push('about')
  return keys.map((key) => ({
    key,
    ...sectionMeta[key],
  }))
})

function openSection(section: MineSection) {
  if (isAdminOnlySection(section) && !isAdmin.value) return
  void router.push({ name: sectionMeta[section].routeName })
}

function onLogout() {
  confirmLogout(modal, logout)
}
</script>

<template>
  <!-- Phone: settings hub -->
  <n-scrollbar v-if="isPhone" class="mobile-mine-scroll" trigger="hover">
    <n-card size="small" :bordered="false" class="mobile-profile-card">
      <n-thing
        class="mobile-profile-thing"
        :title="profileTitle"
      >
        <template #avatar>
          <n-avatar :size="52" round>
            <n-icon :component="PersonOutline" :size="26" />
          </n-avatar>
        </template>
        <template #description>
          <n-space :size="6">
            <n-tag size="small" :type="isAdmin ? 'error' : 'info'">
              {{ roleLabel }}
            </n-tag>
            <n-tag size="small" :color="inactiveVipTagColor">VIP 未开通</n-tag>
          </n-space>
        </template>
      </n-thing>
      <n-button
        v-if="isLoggedIn"
        size="small"
        type="error"
        secondary
        @click="onLogout"
      >
        退出
      </n-button>
      <n-button v-else size="small" type="primary" @click="openLogin">
        登录
      </n-button>
    </n-card>

    <n-card
      size="small"
      :bordered="false"
      content-style="padding: 0;"
      class="mobile-settings-card"
      aria-label="我的功能"
    >
      <n-list hoverable clickable>
        <n-list-item
          v-for="item in mobileSections"
          :key="item.key"
          @click="openSection(item.key)"
        >
          <template #prefix>
            <n-icon :component="item.icon" :size="21" />
          </template>
          <n-thing :title="item.title" />
          <template #suffix>
            <n-icon :component="ChevronForwardOutline" :size="18" />
          </template>
        </n-list-item>
      </n-list>
    </n-card>
  </n-scrollbar>

  <!-- Desktop: account detail -->
  <MineSectionBody v-else>
    <n-card size="small" :bordered="false">
      <template v-if="isLoggedIn">
        <n-thing :title="profileTitle">
          <template #avatar>
            <n-avatar :size="52" round>
              <n-icon :component="PersonOutline" :size="25" />
            </n-avatar>
          </template>
          <template #description>
            <n-space :size="6">
              <n-tag size="small" :type="isAdmin ? 'error' : 'info'">
                {{ roleLabel }}
              </n-tag>
              <n-tag size="small" :color="inactiveVipTagColor">VIP 未开通</n-tag>
            </n-space>
          </template>
          <template #header-extra>
            <n-button size="small" type="error" secondary @click="onLogout">
              <template #icon>
                <n-icon :component="LogOutOutline" />
              </template>
              退出
            </n-button>
          </template>
        </n-thing>
      </template>
      <template v-else>
        <n-thing title="未登录">
          <template #avatar>
            <n-avatar :size="52" round>
              <n-icon :component="PersonOutline" :size="25" />
            </n-avatar>
          </template>
          <template #description>
            <n-space :size="6">
              <n-tag size="small" type="info">{{ roleLabel }}</n-tag>
              <n-tag size="small" :color="inactiveVipTagColor">VIP 未开通</n-tag>
            </n-space>
          </template>
          <template #header-extra>
            <n-button size="small" type="primary" @click="openLogin">
              <template #icon>
                <n-icon :component="LogInOutline" />
              </template>
              登录
            </n-button>
          </template>
        </n-thing>
      </template>
    </n-card>

    <n-card
      v-if="isLoggedIn"
      size="small"
      title="账号说明"
      :bordered="false"
      :segmented="{ content: true }"
    >
      <n-alert type="info" :show-icon="false">
        登录会话由服务端安全 Cookie 维护；退出后不会删除账号下已保存的数据。
      </n-alert>
    </n-card>
  </MineSectionBody>
</template>

<style scoped>
.mobile-mine-scroll {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.mobile-profile-card {
  overflow: hidden;
}

/* 账号信息占满左侧，登录/退出贴右，长用户名不挤按钮 */
.mobile-profile-card :deep(.n-card-content) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mobile-profile-thing {
  min-width: 0;
}

.mobile-settings-card {
  margin-top: 14px;
  overflow: hidden;
  cursor: pointer;
}
</style>
