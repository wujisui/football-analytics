<script setup lang="ts">
import {
  CalendarOutline,
  FlashOutline,
  MoonOutline,
  PersonOutline,
  StarOutline,
  StatsChartOutline,
  SunnyOutline,
} from '@vicons/ionicons5'
import {
  NButton,
  NButtonGroup,
  NConfigProvider,
  NIcon,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NMessageProvider,
  zhCN,
  dateZhCN,
} from 'naive-ui'
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthSession } from '@/composables/useAuthSession'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useTheme } from '@/composables/useTheme'
import LoginModal from '@/views/Mine/components/LoginModal.vue'
import { parseDetailFrom } from '@/utils/detailNav'
import { fixturesRouteWithLeague } from '@/utils/fixturesLeagueFilter'
import { officialSyncing } from '@/layouts/composables/useFixturesShell'

type NavKey = 'home' | 'favorites' | 'predictions' | 'results' | 'mine'

const route = useRoute()
const router = useRouter()
const isPhone = useIsPhone()
const { naiveTheme, themeOverrides, isDark, toggleTheme } = useTheme()
const { isLoggedIn, openLogin } = useAuthSession()

const showBottomNav = computed(
  () => isPhone.value && route.name !== 'fixture-detail',
)

/** Desktop: 「我的」 only after login; otherwise show 登录. Mobile always has Mine. */
const showDesktopMine = computed(() => !isPhone.value && isLoggedIn.value)
const showDesktopLogin = computed(() => !isPhone.value && !isLoggedIn.value)

const activeNav = computed<NavKey>(() => {
  if (route.name === 'mine') return 'mine'
  if (route.name === 'favorites') return 'favorites'
  if (route.name === 'results') return 'results'
  if (route.name === 'predictions') return 'predictions'
  if (route.name === 'fixture-detail') {
    const from = parseDetailFrom(route.query.from)
    if (from === 'results') return 'results'
    if (from === 'predictions') return 'predictions'
    if (from === 'favorites') return 'favorites'
  }
  return 'home'
})

function navType(key: NavKey) {
  return activeNav.value === key ? 'primary' : 'default'
}

function goNav(name: 'home' | 'favorites' | 'predictions' | 'results') {
  if (route.name === name) return
  if (name === 'favorites') {
    void router.push({ name: 'favorites' })
    return
  }
  void router.push(fixturesRouteWithLeague(name))
}

function goMine() {
  if (!isPhone.value && !isLoggedIn.value) {
    openLogin()
    return
  }
  if (route.name === 'mine') return
  void router.push({ name: 'mine' })
}

/** Desktop deep-link /mine while logged out → home + login form. */
watch(
  [() => route.name, isPhone, isLoggedIn],
  ([name, phone, loggedIn]) => {
    if (name !== 'mine' || phone || loggedIn) return
    openLogin()
    void router.replace({ name: 'home' })
  },
  { immediate: true },
)

const bottomItems: {
  key: NavKey
  label: string
  icon: typeof FlashOutline
  onClick: () => void
}[] = [
  { key: 'home', label: '即时', icon: FlashOutline, onClick: () => goNav('home') },
  {
    key: 'predictions',
    label: '计算器',
    icon: StatsChartOutline,
    onClick: () => goNav('predictions'),
  },
  {
    key: 'favorites',
    label: '收藏',
    icon: StarOutline,
    onClick: () => goNav('favorites'),
  },
  {
    key: 'results',
    label: '赛程',
    icon: CalendarOutline,
    onClick: () => goNav('results'),
  },
  { key: 'mine', label: '我的', icon: PersonOutline, onClick: goMine },
]
</script>

<template>
  <n-config-provider
    :locale="zhCN"
    :date-locale="dateZhCN"
    :theme="naiveTheme"
    :theme-overrides="themeOverrides"
  >
    <n-message-provider>
      <n-layout
        class="app-shell"
        :class="{ 'has-bottom-nav': showBottomNav }"
        position="absolute"
        content-style="display: flex; flex-direction: column; height: 100%;"
      >
        <n-layout-header bordered class="app-header">
          <div class="app-header-inner">
            <div
              class="brand"
              role="link"
              tabindex="0"
              @click="goNav('home')"
              @keydown.enter="goNav('home')"
            >
              <span class="brand-title">Football Analytics</span>
              <span class="brand-subtitle">赛前分析 · 人机协同</span>
            </div>

            <div v-if="officialSyncing" class="header-sync-status" role="status">
              <span class="header-sync-dot" aria-hidden="true" />
              <span>正在从官方同步…</span>
            </div>

            <div class="header-actions">
              <n-button-group v-if="!isPhone" size="small">
                <n-button :type="navType('home')" @click="goNav('home')">即时</n-button>
                <n-button
                  :type="navType('predictions')"
                  @click="goNav('predictions')"
                >
                  计算器
                </n-button>
                <n-button
                  :type="navType('favorites')"
                  @click="goNav('favorites')"
                >
                  收藏
                </n-button>
                <n-button :type="navType('results')" @click="goNav('results')">赛程</n-button>
                <n-button
                  v-if="showDesktopMine"
                  :type="navType('mine')"
                  @click="goMine"
                >
                  我的
                </n-button>
              </n-button-group>

              <n-button
                v-if="showDesktopLogin"
                size="small"
                type="primary"
                @click="openLogin"
              >
                登录
              </n-button>

              <n-button
                size="small"
                quaternary
                :aria-label="isDark ? '切换到浅色' : '切换到深色'"
                @click="toggleTheme"
              >
                <template #icon>
                  <n-icon :component="isDark ? MoonOutline : SunnyOutline" />
                </template>
              </n-button>
            </div>
          </div>
        </n-layout-header>

        <n-layout-content
          class="app-body"
          content-style="height: 100%; overflow: hidden; position: relative;"
        >
          <router-view />
        </n-layout-content>

        <nav
          v-if="showBottomNav"
          class="bottom-nav"
          aria-label="主导航"
        >
          <button
            v-for="item in bottomItems"
            :key="item.key"
            type="button"
            class="bottom-nav-item"
            :class="{ active: activeNav === item.key }"
            :aria-current="activeNav === item.key ? 'page' : undefined"
            @click="item.onClick"
          >
            <n-icon :component="item.icon" :size="20" />
            <span>{{ item.label }}</span>
          </button>
        </nav>
      </n-layout>
      <LoginModal />
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
.app-shell {
  inset: 0;
  background: var(--fa-bg);
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 56px;
  box-sizing: border-box;
  padding: env(safe-area-inset-top, 0px) max(16px, env(safe-area-inset-right, 0px)) 0
    max(16px, env(safe-area-inset-left, 0px));
  flex-shrink: 0;
  overflow: hidden;
  background: var(--fa-bg-elevated);
}

.app-header-inner {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  max-width: var(--fa-page-max-width);
  height: 100%;
  box-sizing: border-box;
}

.header-sync-status {
  position: absolute;
  left: 50%;
  top: 50%;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 5px;
  max-width: 40%;
  color: var(--fa-text-muted);
  font-size: 12px;
  white-space: nowrap;
  transform: translate(-50%, -50%);
  pointer-events: none;
}

/* Static marker — avoid n-spin's continuous CSS animation during long syncs. */
.header-sync-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--fa-highlight-text, #c2410c);
}

.brand {
  display: flex;
  flex-direction: column;
  cursor: pointer;
  outline: none;
  flex: 0 1 auto;
  min-width: 0;
}

.brand:focus-visible {
  opacity: 0.8;
}

.brand-title {
  font-size: 17px;
  font-weight: 700;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brand-subtitle {
  font-size: 11px;
  opacity: 0.65;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 4px;
  margin-left: 8px;
}

.app-body {
  flex: 1;
  min-height: 0;
}

.bottom-nav {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  align-items: stretch;
  gap: 0;
  min-height: 52px;
  padding: 4px max(8px, env(safe-area-inset-right, 0px))
    max(4px, env(safe-area-inset-bottom, 0px)) max(8px, env(safe-area-inset-left, 0px));
  border-top: 1px solid var(--fa-border);
  background: var(--fa-bg-elevated);
  box-sizing: border-box;
}

.bottom-nav-item {
  appearance: none;
  border: 0;
  background: transparent;
  color: var(--fa-text-muted, rgba(128, 128, 128, 0.9));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 4px 2px;
  font-size: 11px;
  line-height: 1.2;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.bottom-nav-item.active {
  color: var(--n-color-target, var(--fa-highlight-text));
  font-weight: 600;
}

@media (max-width: 767px) {
  .app-header {
    height: 48px;
    padding-left: max(12px, env(safe-area-inset-left, 0px));
    padding-right: max(12px, env(safe-area-inset-right, 0px));
  }

  .brand {
    max-width: calc(100% - 96px);
  }

  .brand-title {
    font-size: 15px;
  }

  .brand-subtitle {
    display: none;
  }

  .header-sync-status {
    max-width: calc(100% - 190px);
    overflow: hidden;
  }

  .header-sync-status span {
    overflow: hidden;
    text-overflow: ellipsis;
  }
}
</style>
