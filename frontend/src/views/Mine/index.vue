<script setup lang="ts">
import {
  BookmarkOutline,
  ColorPaletteOutline,
  InformationCircleOutline,
  LogInOutline,
  LogOutOutline,
  MoonOutline,
  PersonOutline,
  StarOutline,
  SunnyOutline,
} from '@vicons/ionicons5'
import { NIcon, type MenuOption } from 'naive-ui'
import { computed, h, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthSession } from '@/composables/useAuthSession'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useTheme } from '@/composables/useTheme'
import FavoritesView from '@/views/Favorites/index.vue'
import PlansView from '@/views/Plans/index.vue'
import pkg from '../../../package.json'

defineOptions({ name: 'Mine' })

type MineSection = 'account' | 'favorites' | 'plans' | 'theme' | 'session' | 'about'

const sectionMeta: Record<
  MineSection,
  { routeName: string; title: string; description: string }
> = {
  account: {
    routeName: 'mine-account',
    title: '个人主页',
    description: '查看当前账号状态与基础信息',
  },
  favorites: {
    routeName: 'mine-favorites',
    title: '关注',
    description: '按比赛日期查看关注场次',
  },
  plans: {
    routeName: 'mine-plans',
    title: '我的方案',
    description: '查看和管理已保存的投注方案',
  },
  theme: {
    routeName: 'mine-theme',
    title: '主题设置',
    description: '设置界面的显示主题',
  },
  session: {
    routeName: 'mine-session',
    title: '登录与退出',
    description: '管理当前浏览器的登录状态',
  },
  about: {
    routeName: 'mine-about',
    title: '关于',
    description: 'Football Analytics 产品与版本信息',
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
        icon: renderIcon(PersonOutline),
      },
    ],
  },
  {
    type: 'group',
    key: 'group-data',
    label: '本地数据',
    children: [
      {
        key: 'favorites',
        label: '关注',
        icon: renderIcon(StarOutline),
      },
      {
        key: 'plans',
        label: '我的方案',
        icon: renderIcon(BookmarkOutline),
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
        icon: renderIcon(ColorPaletteOutline),
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
        key: 'about',
        label: '关于',
        icon: renderIcon(InformationCircleOutline),
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
const isEmbeddedSection = computed(
  () => activeSection.value === 'favorites' || activeSection.value === 'plans',
)

const profileTitle = computed(() =>
  isLoggedIn.value ? username.value : 'Football Analytics',
)
const profileDescription = computed(() =>
  isLoggedIn.value ? '已登录' : '暂未登录',
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
      <aside class="mine-sider">
        <div class="profile-summary">
          <n-avatar :size="48" round>
            <n-icon :component="PersonOutline" :size="24" />
          </n-avatar>
          <div class="profile-summary__text">
            <strong>{{ profileTitle }}</strong>
            <span>{{ profileDescription }}</span>
          </div>
        </div>

        <n-scrollbar class="mine-menu-scroll" trigger="hover" x-scrollable>
          <n-menu
            class="mine-menu"
            :value="activeSection"
            :options="menuOptions"
            :mode="isPhone ? 'horizontal' : 'vertical'"
            :indent="20"
            @update:value="openSection"
          />
        </n-scrollbar>
      </aside>

      <main class="mine-main">
        <div v-if="isEmbeddedSection" class="mine-embedded">
          <FavoritesView v-if="activeSection === 'favorites'" />
          <PlansView v-else />
        </div>

        <header v-if="!isEmbeddedSection" class="mine-header">
          <h1>{{ activeMeta.title }}</h1>
          <p>{{ activeMeta.description }}</p>
        </header>

        <n-scrollbar
          v-if="!isEmbeddedSection"
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
                        ? '偏好、关注与方案当前保存在本机'
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

.profile-summary__text strong,
.profile-summary__text span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  flex-shrink: 0;
  min-height: 92px;
  padding: 18px 28px;
  border-bottom: 1px solid var(--fa-border);
  background: var(--fa-bg-elevated);
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

@media (max-width: 767px) {
  .mine-shell {
    flex-direction: column;
  }

  .mine-sider {
    flex: 0 0 auto;
    width: 100%;
    box-shadow: var(--fa-header-shadow);
  }

  .profile-summary {
    min-height: 64px;
    padding: 8px 12px;
  }

  .profile-summary :deep(.n-avatar) {
    width: 38px !important;
    height: 38px !important;
  }

  .mine-menu-scroll {
    flex: none;
  }

  .mine-menu {
    width: max-content;
    min-width: 100%;
    padding: 0 6px;
  }

  .mine-header {
    min-height: 70px;
    padding: 12px var(--fa-content-inline);
  }

  .mine-header h1 {
    font-size: 18px;
  }

  .mine-content {
    padding: 14px var(--fa-content-inline) 24px;
  }
}
</style>
