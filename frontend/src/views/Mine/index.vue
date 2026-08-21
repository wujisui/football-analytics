<script setup lang="ts">
import { ChevronBackOutline } from '@vicons/ionicons5'
import { NIcon, type MenuOption } from 'naive-ui'
import { computed, h, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthSession } from '@/composables/useAuthSession'
import { useBetPlans } from '@/composables/useBetPlans'
import { useIsPhone } from '@/composables/useMediaQuery'
import ShellBreadcrumb from '@/layouts/components/ShellBreadcrumb.vue'
import FavoriteDatesPicker from '@/views/Favorites/components/FavoriteDatesPicker.vue'
import {
  sectionFromRouteName,
  sectionMeta,
  type MineSection,
} from '@/views/Mine/sectionMeta'

defineOptions({ name: 'Mine' })

const route = useRoute()
const router = useRouter()
const isPhone = useIsPhone()
const { isAdmin } = useAuthSession()
const { filterDate, planDays, plansForDay } = useBetPlans()

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
        label: '主题与玩法',
        icon: renderIcon(sectionMeta.theme.icon),
      },
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
              key: 'hotLeagues',
              label: '热门联赛',
              icon: renderIcon(sectionMeta.hotLeagues.icon),
            } satisfies MenuOption,
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
const dayPlanCountLabel = computed(
  () => `已保存 ${plansForDay(filterDate.value).length} 个方案`,
)
/** PC 顶栏第二行左侧：方案页给统计，其余分区给说明文案，保证面包屑高度一致 */
const sectionMetaLine = computed(() =>
  isPlansSection.value ? dayPlanCountLabel.value : (activeMeta.value.hint ?? ''),
)
/** PC 二级页 / 手机二级页：共用同一顶栏，手机个人主页不显示 */
const showSectionHeader = computed(
  () =>
    (isPhone.value && activeSection.value !== 'account') || !isPhone.value,
)

function isAdminSection(section: string): boolean {
  return section === 'admin' || section === 'hotLeagues'
}

function openSection(section: string) {
  if (!(section in sectionMeta)) return
  if (isAdminSection(section) && !isAdmin.value) return
  const mineSection = section as MineSection
  const target = sectionMeta[mineSection].routeName
  if (route.name !== target) void router.push({ name: target })
}

watch(
  () => [activeSection.value, isAdmin.value] as const,
  ([section, admin]) => {
    if (isAdminSection(section) && !admin) {
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
          <!-- 手机：标题居中，返回键叠在左侧；统计/日期由各分区自己承载 -->
          <div v-if="isPhone" class="fa-toolbar-top fa-toolbar-centered">
            <n-button
              class="fa-toolbar-back"
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
            <span class="fa-toolbar-title">{{ activeMeta.title }}</span>
          </div>

          <!-- PC 对齐比赛/关注：面包屑在上，统计（或说明）与方案日期在下 -->
          <template v-else>
            <div class="fa-toolbar-top">
              <ShellBreadcrumb
                root-label="我的"
                :filter-label="activeMeta.title"
                @select-root="openSection('account')"
              />
            </div>
            <div class="fa-toolbar-list-meta">
              <span class="fa-toolbar-day-stat mine-meta-line">
                {{ sectionMetaLine }}
              </span>
              <FavoriteDatesPicker
                v-if="isPlansSection"
                v-model="filterDate"
                :marked-days="planDays"
                legend="当天有方案（赛程日）"
              />
            </div>
          </template>
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
  box-shadow: var(--fa-header-shadow);
}

.mine-meta-line {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--fa-text-secondary);
}

/* 【我的】设置项统一用「标题 → 次级说明」两层，避免说明与标题抢层级。 */
.mine-outlet :deep(.n-thing-main__description) {
  color: var(--fa-text-secondary);
  font-size: 13px;
  line-height: 1.55;
}

.mine-header :deep(.n-breadcrumb-item:first-child .n-breadcrumb-item__link) {
  cursor: pointer;
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
</style>
