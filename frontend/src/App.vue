<script setup lang="ts">
import {
  CalendarOutline,
  PersonOutline,
  StarOutline,
  StatsChartOutline,
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
  NModalProvider,
  zhCN,
  dateZhCN,
} from 'naive-ui'
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthSession } from '@/composables/useAuthSession'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useTheme } from '@/composables/useTheme'
import HandicapRulesetSwitch from '@/components/HandicapRulesetSwitch.vue'
import LoginModal from '@/views/Mine/components/LoginModal.vue'
import { parseDetailFrom } from '@/utils/detailNav'
import { fixturesRouteWithLeague } from '@/utils/fixturesLeagueFilter'

type NavKey = 'predictions' | 'results' | 'favorites' | 'mine'

const route = useRoute()
const router = useRouter()
const isPhone = useIsPhone()
const { naiveTheme, themeOverrides } = useTheme()
const { verifySession } = useAuthSession()

onMounted(() => {
  void verifySession()
})

/** 详情页、以及【我的】二级页（不含个人主页）自动隐藏底栏。 */
function hidesPhoneBottomNav(name: unknown): boolean {
  const n = String(name ?? '')
  if (n === 'fixture-detail') return true
  return n.startsWith('mine-') && n !== 'mine-account'
}

const showBottomNav = computed(
  () => isPhone.value && !hidesPhoneBottomNav(route.name),
)

function isMineRoute(name: unknown) {
  return String(name ?? '').startsWith('mine')
}

const activeNav = computed<NavKey>(() => {
  if (isMineRoute(route.name)) return 'mine'
  if (route.name === 'favorites') return 'favorites'
  if (route.name === 'results') return 'results'
  if (route.name === 'predictions') return 'predictions'
  if (route.name === 'fixture-detail') {
    const from = parseDetailFrom(route.query.from)
    if (from === 'results') return 'results'
    if (from === 'predictions') return 'predictions'
    if (from === 'favorites') return 'favorites'
  }
  return 'predictions'
})

function navType(key: NavKey) {
  return activeNav.value === key ? 'primary' : 'default'
}

function goNav(name: 'predictions' | 'results') {
  if (route.name === name) return
  void router.push(fixturesRouteWithLeague(name))
}

function goMine() {
  if (route.name === 'mine-account') return
  void router.push({ name: 'mine-account' })
}

function goFavorites() {
  if (route.name === 'favorites') return
  void router.push({ name: 'favorites' })
}

const bottomItems: {
  key: NavKey
  label: string
  icon: typeof StatsChartOutline
  onClick: () => void
}[] = [
  {
    key: 'predictions',
    label: '计算器',
    icon: StatsChartOutline,
    onClick: () => goNav('predictions'),
  },
  {
    key: 'results',
    label: '赛程',
    icon: CalendarOutline,
    onClick: () => goNav('results'),
  },
  { key: 'favorites', label: '关注', icon: StarOutline, onClick: goFavorites },
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
      <n-modal-provider>
        <n-layout
          class="app-shell"
          position="absolute"
          content-style="display: flex; flex-direction: column; height: 100%;"
        >
          <!-- Phone uses bottom nav; hide top brand/header to free content height. -->
          <n-layout-header v-if="!isPhone" class="app-header">
            <div class="app-header-inner">
              <div
                class="brand"
                role="link"
                tabindex="0"
                @click="goNav('predictions')"
                @keydown.enter="goNav('predictions')"
              >
                <n-ellipsis class="brand-title">Football Analytics</n-ellipsis>
                <n-ellipsis class="brand-subtitle">赛前分析 · 人机协同</n-ellipsis>
              </div>

              <div class="header-actions">
                <n-button-group size="small">
                  <n-button
                    :type="navType('predictions')"
                    @click="goNav('predictions')"
                  >
                    比赛
                  </n-button>
                  <n-button :type="navType('results')" @click="goNav('results')">赛程</n-button>
                  <n-button :type="navType('favorites')" @click="goFavorites">关注</n-button>
                  <n-button :type="navType('mine')" @click="goMine">
                    我的
                  </n-button>
                </n-button-group>

                <HandicapRulesetSwitch class="ruleset-switch" />
              </div>
            </div>
          </n-layout-header>

          <n-layout-content
            class="app-body"
            content-style="height: 100%; overflow: hidden; position: relative;"
          >
            <router-view v-slot="{ Component }">
              <keep-alive :include="['FixturesShellLayout', 'Favorites', 'Mine']">
                <component :is="Component" />
              </keep-alive>
            </router-view>
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
      </n-modal-provider>
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
  position: relative;
  z-index: 3;
  height: 56px;
  box-sizing: border-box;
  padding: env(safe-area-inset-top, 0px) max(16px, env(safe-area-inset-right, 0px)) 0
    max(16px, env(safe-area-inset-left, 0px));
  flex-shrink: 0;
  overflow: hidden;
  background: var(--fa-bg-elevated);
  box-shadow: var(--fa-header-shadow);
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
}

.brand-subtitle {
  font-size: 11px;
  opacity: 0.65;
  line-height: 1.2;
}

.header-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 4px;
  margin-left: 8px;
}

.ruleset-switch {
  margin-left: 4px;
}

.app-body {
  flex: 1;
  min-height: 0;
}

.bottom-nav {
  position: relative;
  z-index: 3;
  flex-shrink: 0;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  align-items: stretch;
  gap: 0;
  min-height: 52px;
  padding: 4px max(8px, env(safe-area-inset-right, 0px))
    max(4px, env(safe-area-inset-bottom, 0px)) max(8px, env(safe-area-inset-left, 0px));
  background: var(--fa-bg-elevated);
  box-shadow: var(--fa-bottom-nav-shadow);
  box-sizing: border-box;
  /* 不可选由全局触屏规则统一负责（style.css @media pointer: coarse） */
  touch-action: manipulation;
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
  touch-action: manipulation;
}

.bottom-nav-item.active {
  color: var(--fa-highlight-text);
  font-weight: 600;
}

/* Phone: no top header — keep content clear of notch / status bar. */
@media (max-width: 767px) {
  .app-body {
    padding-top: env(safe-area-inset-top, 0px);
  }
}
</style>
