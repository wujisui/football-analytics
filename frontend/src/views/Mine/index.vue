<script setup lang="ts">
import {
  ChevronBackOutline,
  ChevronForwardOutline,
  BookmarkOutline,
  ColorPaletteOutline,
  InformationCircleOutline,
  LogInOutline,
  LogOutOutline,
  MoonOutline,
  PersonOutline,
  SettingsOutline,
  SunnyOutline,
} from '@vicons/ionicons5'
import { NIcon, type MenuOption } from 'naive-ui'
import { computed, h, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthSession } from '@/composables/useAuthSession'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useTheme } from '@/composables/useTheme'
import AdminOpsPanel from '@/views/Mine/components/AdminOpsPanel.vue'
import PlansView from '@/views/Plans/index.vue'
import pkg from '../../../package.json'

defineOptions({ name: 'Mine' })

type MineSection = 'account' | 'plans' | 'theme' | 'session' | 'admin' | 'about'

const sectionMeta: Record<
  MineSection,
  { routeName: string; title: string; description: string; icon: Component }
> = {
  account: {
    routeName: 'mine-account',
    title: '个人主页',
    description: '查看当前账号状态与基础信息',
    icon: PersonOutline,
  },
  plans: {
    routeName: 'mine-plans',
    title: '我的方案',
    description: '查看和管理已保存的投注方案',
    icon: BookmarkOutline,
  },
  theme: {
    routeName: 'mine-theme',
    title: '主题设置',
    description: '设置界面的显示主题',
    icon: ColorPaletteOutline,
  },
  session: {
    routeName: 'mine-session',
    title: '登录与退出',
    description: '管理当前浏览器的登录状态',
    icon: LogOutOutline,
  },
  admin: {
    routeName: 'mine-admin',
    title: '管理员设置',
    description: '运维开关（需 ADMIN_API_KEY）',
    icon: SettingsOutline,
  },
  about: {
    routeName: 'mine-about',
    title: '关于',
    description: 'Football Analytics 产品与版本信息',
    icon: InformationCircleOutline,
  },
}

const route = useRoute()
const router = useRouter()
const isPhone = useIsPhone()
const { isDark, toggleTheme } = useTheme()
const { isLoggedIn, username, openLogin, logout } = useAuthSession()

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
      {
        key: 'session',
        label: isLoggedIn.value ? '退出登录' : '登录账号',
        icon: renderIcon(isLoggedIn.value ? LogOutOutline : LogInOutline),
      },
    ],
  },
  {
    type: 'group',
    key: 'group-other',
    label: '其他',
    children: [
      {
        key: 'admin',
        label: '管理员设置',
        icon: renderIcon(sectionMeta.admin.icon),
      },
      {
        key: 'about',
        label: '关于',
        icon: renderIcon(sectionMeta.about.icon),
      },
    ],
  },
])

const activeSection = computed<MineSection>(() => {
  const matched = Object.entries(sectionMeta).find(
    ([, meta]) => meta.routeName === route.name,
  )
  return (matched?.[0] as MineSection | undefined) ?? 'account'
})
const activeMeta = computed(() => sectionMeta[activeSection.value])
const isPlansSection = computed(() => activeSection.value === 'plans')
/** PC 非嵌入区 / 手机二级页：共用同一顶栏，手机多一个返回 */
const showSectionHeader = computed(
  () =>
    (isPhone.value && activeSection.value !== 'account') ||
    (!isPhone.value && !isPlansSection.value),
)

const profileTitle = computed(() =>
  isLoggedIn.value ? username.value : 'Football Analytics',
)
const profileDescription = computed(() =>
  isLoggedIn.value ? '已登录' : '暂未登录',
)
const mobileSections = computed(() =>
  (['plans', 'theme', 'session', 'admin', 'about'] as MineSection[]).map((key) => ({
    key,
    ...sectionMeta[key],
    title:
      key === 'session'
        ? isLoggedIn.value
          ? '退出登录'
          : '登录账号'
        : sectionMeta[key].title,
    icon:
      key === 'session'
        ? isLoggedIn.value
          ? LogOutOutline
          : LogInOutline
        : sectionMeta[key].icon,
  })),
)

function openSection(section: string) {
  if (!(section in sectionMeta)) return
  const mineSection = section as MineSection
  const target = sectionMeta[mineSection].routeName
  if (route.name !== target) void router.push({ name: target })
}

function onLogout() {
  logout()
  if (!isPhone.value) void router.replace({ name: 'predictions' })
}
</script>

<template>
  <div class="fa-page-frame">
    <div class="fa-page-shell mine-shell">
      <aside v-if="!isPhone" class="mine-sider">
        <div class="profile-summary">
          <n-avatar :size="48" round>
            <n-icon :component="PersonOutline" :size="24" />
          </n-avatar>
          <div class="profile-summary__text">
            <n-ellipsis>
              <strong>{{ profileTitle }}</strong>
            </n-ellipsis>
            <n-ellipsis>
              <span>{{ profileDescription }}</span>
            </n-ellipsis>
          </div>
        </div>

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
      </aside>

      <main class="mine-main">
        <n-scrollbar
          v-if="isPhone && activeSection === 'account'"
          class="mobile-mine-scroll"
          trigger="hover"
        >
          <div class="mobile-mine-home">
            <section class="mobile-profile-card">
              <n-avatar :size="52" round>
                <n-icon :component="PersonOutline" :size="26" />
              </n-avatar>
              <div class="mobile-profile-copy">
                <n-ellipsis>
                  <strong>{{ profileTitle }}</strong>
                </n-ellipsis>
                <n-ellipsis>
                  <span>
                    {{
                      isLoggedIn
                        ? '方案与偏好保存在本机'
                        : '登录后可同步账号状态'
                    }}
                  </span>
                </n-ellipsis>
              </div>
              <n-tag v-if="isLoggedIn" size="small" type="success">已登录</n-tag>
              <n-button v-else size="small" type="primary" @click="openLogin">
                登录
              </n-button>
            </section>

            <section class="mobile-settings-card" aria-label="我的功能">
              <button
                v-for="item in mobileSections"
                :key="item.key"
                type="button"
                class="mobile-settings-row"
                @click="openSection(item.key)"
              >
                <span class="mobile-settings-icon">
                  <n-icon :component="item.icon" :size="21" />
                </span>
                <span class="mobile-settings-copy">
                  <strong>{{ item.title }}</strong>
                  <n-ellipsis>
                    <small>{{ item.description }}</small>
                  </n-ellipsis>
                </span>
                <n-icon
                  :component="ChevronForwardOutline"
                  :size="18"
                  class="mobile-settings-arrow"
                />
              </button>
            </section>

            <p class="mobile-local-note">
              服务端鉴权仍在规划中，当前登录状态仅保存在本机浏览器。
            </p>
          </div>
        </n-scrollbar>

        <header v-if="showSectionHeader" class="mine-header">
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
        </header>

        <div v-if="isPlansSection" class="mine-embedded">
          <PlansView />
        </div>

        <n-scrollbar
          v-if="!isPlansSection && !(isPhone && activeSection === 'account')"
          class="mine-content-scroll"
          trigger="hover"
        >
          <div class="mine-content">
            <template v-if="activeSection === 'account'">
              <n-card size="small" :bordered="false">
                <n-thing :title="profileTitle">
                  <template #avatar>
                    <n-avatar :size="52" round>
                      <n-icon :component="PersonOutline" :size="25" />
                    </n-avatar>
                  </template>
                  <template #description>
                    {{
                      isLoggedIn
                        ? '偏好与方案当前保存在本机'
                        : '登录后可使用桌面端“我的”入口'
                    }}
                  </template>
                  <template #header-extra>
                    <n-tag v-if="isLoggedIn" size="small" type="success">已登录</n-tag>
                    <n-button v-else size="small" type="primary" @click="openLogin">
                      <template #icon>
                        <n-icon :component="LogInOutline" />
                      </template>
                      登录
                    </n-button>
                  </template>
                </n-thing>
              </n-card>

              <n-card size="small" title="账号说明" :bordered="false">
                <n-alert type="info" :show-icon="false">
                  服务端鉴权仍在规划中，当前登录状态仅保存在本机浏览器。
                </n-alert>
              </n-card>
            </template>

            <template v-else-if="activeSection === 'theme'">
              <n-card size="small" title="主题" :bordered="false">
                <n-list>
                  <n-list-item>
                    <template #prefix>
                      <n-icon
                        :component="isDark ? MoonOutline : SunnyOutline"
                        :size="20"
                      />
                    </template>
                    <n-thing
                      title="深色模式"
                      description="与顶栏主题开关同步，偏好保存在本机"
                    />
                    <template #suffix>
                      <n-switch
                        :value="isDark"
                        aria-label="深色模式"
                        @update:value="toggleTheme"
                      />
                    </template>
                  </n-list-item>
                </n-list>
              </n-card>
            </template>

            <template v-else-if="activeSection === 'admin'">
              <AdminOpsPanel />
            </template>

            <template v-else-if="activeSection === 'session'">
              <n-card size="small" title="账号" :bordered="false">
                <n-list>
                  <n-list-item v-if="!isLoggedIn">
                    <template #prefix>
                      <n-icon :component="LogInOutline" :size="20" />
                    </template>
                    <n-thing title="登录账号" description="打开登录表单" />
                    <template #suffix>
                      <n-button size="small" type="primary" @click="openLogin">
                        登录
                      </n-button>
                    </template>
                  </n-list-item>
                  <n-list-item v-else>
                    <template #prefix>
                      <n-icon :component="LogOutOutline" :size="20" />
                    </template>
                    <n-thing
                      title="退出登录"
                      :description="
                        isPhone
                          ? '退出后仍可继续使用本地功能'
                          : '退出后桌面端“我的”入口会隐藏'
                      "
                    />
                    <template #suffix>
                      <n-button size="small" @click="onLogout">退出</n-button>
                    </template>
                  </n-list-item>
                </n-list>
              </n-card>
            </template>

            <template v-else>
              <n-card size="small" :bordered="false">
                <n-descriptions
                  label-placement="left"
                  :column="1"
                  size="small"
                  :label-style="{ width: '72px' }"
                >
                  <n-descriptions-item label="定位">
                    赛前分析工具，非实时比分站
                  </n-descriptions-item>
                  <n-descriptions-item label="版本">
                    {{ pkg.version }}
                  </n-descriptions-item>
                  <n-descriptions-item label="数据">
                    仅调用本项目后端；官方 Key 不进入前端
                  </n-descriptions-item>
                  <n-descriptions-item label="账号">
                    手机端可直接进入“我的”；桌面端登录后显示入口
                  </n-descriptions-item>
                </n-descriptions>
              </n-card>
            </template>
          </div>
        </n-scrollbar>
      </main>
    </div>
  </div>
</template>

<style scoped>
.mine-shell {
  display: flex;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--fa-bg);
}

.mine-sider {
  z-index: 1;
  display: flex;
  flex: 0 0 240px;
  flex-direction: column;
  min-width: 0;
  background: var(--fa-bg-elevated);
  box-shadow: var(--fa-sider-shadow);
}

.profile-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 92px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--fa-border);
}

.profile-summary__text {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.profile-summary__text strong {
  color: var(--fa-text-strong);
  font-size: 15px;
}

.profile-summary__text span {
  margin-top: 3px;
  color: var(--fa-text-muted);
  font-size: 12px;
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
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
}

.mine-embedded {
  position: relative;
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.mine-header {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
  min-height: 92px;
  padding: 18px 28px;
  border-bottom: 1px solid var(--fa-border);
  background: var(--fa-bg-elevated);
  box-sizing: border-box;
}

.mine-header__copy {
  min-width: 0;
  flex: 1;
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

.mine-content-scroll {
  flex: 1;
  min-height: 0;
}

.mine-content {
  width: min(100%, 920px);
  padding: 24px 28px 32px;
}

.mine-content > * + * {
  margin-top: 14px;
}

.mobile-mine-scroll {
  flex: 1;
  min-height: 0;
}

.mobile-mine-home {
  padding: 14px var(--fa-content-inline) 28px;
}

.mobile-profile-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 16px;
  border: 1px solid var(--fa-border);
  border-radius: 12px;
  background: var(--fa-bg-elevated);
}

.mobile-profile-copy {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.mobile-profile-copy strong {
  color: var(--fa-text-strong);
  font-size: 16px;
}

.mobile-profile-copy span {
  color: var(--fa-text-muted);
  font-size: 12px;
}

.mobile-settings-card {
  margin-top: 14px;
  overflow: hidden;
  border: 1px solid var(--fa-border);
  border-radius: 12px;
  background: var(--fa-bg-elevated);
}

.mobile-settings-row {
  display: flex;
  width: 100%;
  min-height: 64px;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: 0;
  border-bottom: 1px solid var(--fa-border);
  color: inherit;
  text-align: left;
  background: transparent;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.mobile-settings-row:last-child {
  border-bottom: 0;
}

.mobile-settings-row:active {
  background: var(--fa-bg);
}

.mobile-settings-icon {
  display: inline-flex;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  color: var(--fa-highlight-text);
  background: color-mix(in srgb, var(--fa-highlight-text) 12%, transparent);
}

.mobile-settings-copy {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.mobile-settings-copy strong {
  color: var(--fa-text-strong);
  font-size: 14px;
  font-weight: 500;
}

.mobile-settings-copy small {
  color: var(--fa-text-muted);
  font-size: 11px;
}

.mobile-settings-arrow {
  flex-shrink: 0;
  color: var(--fa-text-muted);
}

.mobile-local-note {
  margin: 14px 8px 0;
  color: var(--fa-text-muted);
  font-size: 11px;
  line-height: 1.6;
  text-align: center;
}

@media (max-width: 767px) {
  .mine-header {
    position: relative;
    justify-content: center;
    min-height: 48px;
    padding: 8px 48px;
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

  .mine-header h1 {
    font-size: 16px;
    line-height: 1.3;
  }

  .mine-content {
    padding: 14px var(--fa-content-inline) 24px;
  }
}
</style>
