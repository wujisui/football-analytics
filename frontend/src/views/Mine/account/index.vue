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

const mobileSections = computed(() => {
  const keys: MineSection[] = ['plans', 'theme']
  if (isAdmin.value) keys.push('admin')
  keys.push('about')
  return keys.map((key) => ({
    key,
    ...sectionMeta[key],
  }))
})

function openSection(section: MineSection) {
  if (section === 'admin' && !isAdmin.value) return
  void router.push({ name: sectionMeta[section].routeName })
}

function onLogout() {
  confirmLogout(modal, logout)
}
</script>

<template>
  <!-- Phone: settings hub -->
  <n-scrollbar v-if="isPhone" class="mobile-mine-scroll" trigger="hover">
    <div class="mobile-mine-home">
      <n-card size="small" :bordered="false" class="mobile-profile-card">
        <n-thing
          :title="profileTitle"
          :description="
            isLoggedIn
              ? '收藏与方案按当前账号保存'
              : '登录后可保存个人收藏与方案'
          "
        >
          <template #avatar>
            <n-avatar :size="52" round>
              <n-icon :component="PersonOutline" :size="26" />
            </n-avatar>
          </template>
          <template #header-extra>
            <n-tag v-if="isLoggedIn" size="small" type="success">已登录</n-tag>
            <n-button v-else size="small" type="primary" @click="openLogin">
              登录
            </n-button>
          </template>
        </n-thing>
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
            <n-thing :title="item.title" :description="item.description" />
            <template #suffix>
              <n-icon :component="ChevronForwardOutline" :size="18" />
            </template>
          </n-list-item>
          <n-list-item v-if="isLoggedIn" @click="onLogout">
            <template #prefix>
              <n-icon :component="LogOutOutline" :size="21" />
            </template>
            <n-thing title="退出登录" description="退出当前账号" />
          </n-list-item>
        </n-list>
      </n-card>
    </div>
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
          <template #description>收藏与方案按当前账号保存</template>
          <template #header-extra>
            <n-tag size="small" type="success">已登录</n-tag>
          </template>
        </n-thing>
      </template>
      <template v-else>
        <n-thing title="未登录" description="登录后可保存个人收藏与方案">
          <template #avatar>
            <n-avatar :size="52" round>
              <n-icon :component="PersonOutline" :size="25" />
            </n-avatar>
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

    <n-card v-if="isLoggedIn" size="small" title="账号说明" :bordered="false">
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

.mobile-mine-home {
  padding: 14px var(--fa-content-inline) 28px;
}

.mobile-profile-card {
  overflow: hidden;
}

.mobile-settings-card {
  margin-top: 14px;
  overflow: hidden;
  cursor: pointer;
}
</style>
