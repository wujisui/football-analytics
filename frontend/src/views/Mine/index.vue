<script setup lang="ts">
import { ChevronBackOutline, LogOutOutline } from '@vicons/ionicons5'
import { NIcon, useModal, type MenuOption } from 'naive-ui'
import { computed, h, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthSession } from '@/composables/useAuthSession'
import { useBetPlans } from '@/composables/useBetPlans'
import { useIsPhone } from '@/composables/useMediaQuery'
import FavoriteDatesPicker from '@/views/Favorites/components/FavoriteDatesPicker.vue'
import { confirmLogout } from '@/views/Mine/confirmLogout'
import {
  sectionFromRouteName,
  sectionMeta,
  type MineSection,
} from '@/views/Mine/sectionMeta'

defineOptions({ name: 'Mine' })

const route = useRoute()
const router = useRouter()
const modal = useModal()
const isPhone = useIsPhone()
const { isLoggedIn, isAdmin, logout } = useAuthSession()
const { filterDate, planDays } = useBetPlans()

function renderIcon(icon: Component) {
  return () => h(NIcon, null, { default: () => h(icon) })
}

const menuOptions = computed<MenuOption[]>(() => [
  {
    type: 'group',
    key: 'group-mine',
    label: '我的',
    children: [
      {
        key: 'account',
        label: '个人主页',
        icon: renderIcon(sectionMeta.account.icon),
      },
    ],
  },
  {
    type: 'group',
    key: 'group-data',
    label: '本地数据',
    children: [
      {
        key: 'plans',
        label: '我的方案',
        icon: renderIcon(sectionMeta.plans.icon),
      },
    ],
  },
  {
    type: 'group',
    key: 'group-preferences',
    label: '账号与偏好',
    children: [
      {
        key: 'theme',
        label: '主题设置',
        icon: renderIcon(sectionMeta.theme.icon),
      },
      ...(isLoggedIn.value
        ? [
            {
              key: 'logout',
              label: '退出登录',
              icon: renderIcon(LogOutOutline),
            } satisfies MenuOption,
          ]
        : []),
    ],
  },
  {
    type: 'group',
    key: 'group-other',
    label: '其他',
    children: [
      ...(isAdmin.value
        ? [
            {
              key: 'admin',
              label: '管理员设置',
              icon: renderIcon(sectionMeta.admin.icon),
            } satisfies MenuOption,
          ]
        : []),
      {
        key: 'about',
        label: '关于',
        icon: renderIcon(sectionMeta.about.icon),
      },
    ],
  },
])

const activeSection = computed(() => sectionFromRouteName(route.name))
const activeMeta = computed(() => sectionMeta[activeSection.value])
const isPlansSection = computed(() => activeSection.value === 'plans')
/** PC 二级页 / 手机二级页：共用同一顶栏，手机个人主页不显示 */
const showSectionHeader = computed(
  () =>
    (isPhone.value && activeSection.value !== 'account') || !isPhone.value,
)

function onLogout() {
  confirmLogout(modal, logout)
}

function openSection(section: string) {
  if (section === 'logout') {
    onLogout()
    return
  }
  if (!(section in sectionMeta)) return
  if (section === 'admin' && !isAdmin.value) return
  const mineSection = section as MineSection
  const target = sectionMeta[mineSection].routeName
  if (route.name !== target) void router.push({ name: target })
}

watch(
  () => [activeSection.value, isAdmin.value] as const,
  ([section, admin]) => {
    if (section === 'admin' && !admin) {
      void router.replace({ name: 'mine-account' })
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="fa-page-frame">
    <n-layout
      :has-sider="!isPhone"
      class="fa-page-shell mine-shell"
      content-style="height: 100%;"
    >
      <n-layout-sider
        v-if="!isPhone"
        class="mine-sider"
        :width="232"
        :native-scrollbar="false"
        content-style="height: 100%; display: flex; flex-direction: column;"
      >
        <n-scrollbar class="mine-menu-scroll" trigger="hover" x-scrollable>
          <n-menu
            class="mine-menu"
            :value="activeSection"
            :options="menuOptions"
            mode="vertical"
            :indent="20"
            @update:value="openSection"
          />
        </n-scrollbar>
      </n-layout-sider>

      <n-layout
        class="mine-main"
        content-style="display: flex; flex-direction: column; height: 100%; min-height: 0; overflow: hidden;"
      >
        <n-layout-header
          v-if="showSectionHeader"
          class="mine-header fa-page-toolbar"
        >
          <n-button
            v-if="isPhone"
            quaternary
            circle
            size="small"
            aria-label="返回"
            @click="openSection('account')"
          >
            <template #icon>
              <n-icon :component="ChevronBackOutline" />
            </template>
          </n-button>
          <div class="mine-header__copy">
            <h1>{{ activeMeta.title }}</h1>
            <p v-if="!isPhone">{{ activeMeta.description }}</p>
          </div>
          <div v-if="isPlansSection" class="mine-header__end">
            <FavoriteDatesPicker
              v-model="filterDate"
              :marked-days="planDays"
              legend="当天有方案（赛程日）"
            />
          </div>
        </n-layout-header>

        <div class="mine-outlet">
          <router-view />
        </div>
      </n-layout>
    </n-layout>
  </div>
</template>

<style scoped>
.mine-shell {
  height: 100%;
  overflow: hidden;
  background: var(--fa-bg);
}

.mine-sider {
  position: relative;
  z-index: 3;
  background: var(--fa-bg-elevated);
  box-shadow: var(--fa-sider-shadow);
}

.mine-menu-scroll {
  flex: 1;
  min-height: 0;
}

.mine-menu {
  padding: 10px 0 18px;
}

.mine-menu :deep(.n-menu-item-group-title) {
  font-size: 12px;
}

.mine-main {
  min-width: 0;
  background: var(--fa-bg);
}

.mine-header {
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: var(--fa-header-shadow);
}

.mine-header__copy {
  min-width: 0;
  flex: 1;
}

.mine-header__end {
  flex-shrink: 0;
}

.mine-header h1 {
  margin: 0;
  color: var(--fa-text-strong);
  font-size: 20px;
  line-height: 1.5;
}

.mine-header p {
  margin: 5px 0 0;
  color: var(--fa-text-muted);
  font-size: 13px;
}

.mine-outlet {
  position: relative;
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.mine-outlet > :deep(*) {
  flex: 1;
  min-height: 0;
  min-width: 0;
}

@media (max-width: 767px) {
  .mine-header {
    position: relative;
    justify-content: center;
    min-height: 48px;
    padding: 8px 56px;
  }

  .mine-header > :deep(.n-button) {
    position: absolute;
    left: 10px;
  }

  .mine-header__copy {
    flex: none;
    max-width: 100%;
    text-align: center;
  }

  .mine-header__end {
    position: absolute;
    right: 10px;
  }

  .mine-header h1 {
    font-size: 16px;
    line-height: 1.3;
  }
}
</style>
