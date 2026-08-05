<script setup lang="ts">
import {
  InformationCircleOutline,
  LogInOutline,
  LogOutOutline,
  MoonOutline,
  PersonOutline,
  StarOutline,
  SunnyOutline,
} from '@vicons/ionicons5'
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthSession } from '@/composables/useAuthSession'
import { useFavoriteFixtures } from '@/composables/useFavoriteFixtures'
import { useIsPhone } from '@/composables/useMediaQuery'
import { useTheme } from '@/composables/useTheme'
import { todayDate } from '@/utils/homeDateStrip'
import { toScheduleDayKey } from '@/utils/format'
import pkg from '../../../package.json'

defineOptions({ name: 'Mine' })

const router = useRouter()
const isPhone = useIsPhone()
const { favorites, reloadFavorites } = useFavoriteFixtures()
const { isDark, toggleTheme } = useTheme()
const { isLoggedIn, username, openLogin, logout } = useAuthSession()

const favoriteCount = computed(() => favorites.value.length)
const todayFavoriteCount = computed(() => {
  const day = todayDate()
  return favorites.value.filter(
    (item) => toScheduleDayKey(item.fixture_date) === day,
  ).length
})

const profileTitle = computed(() =>
  isLoggedIn.value ? username.value : 'Football Analytics',
)

const profileDescription = computed(() =>
  isLoggedIn.value
    ? '已登录 · 偏好与收藏保存在本机'
    : '赛前分析 · 人机协同。登录后可同步账号能力（服务端鉴权待对接）。',
)

function goFavorites() {
  void router.push({ name: 'favorites' })
}

function onLogout() {
  logout()
  // Desktop hides 「我的」 after logout; leave the gated page.
  if (!isPhone.value) void router.replace({ name: 'home' })
}

onMounted(() => {
  void reloadFavorites()
})
</script>

<template>
  <div class="fa-page-frame">
    <div class="fa-page-shell mine-shell">
      <n-scrollbar trigger="hover">
        <div class="fa-page-content-padding mine-body">
          <n-space vertical :size="12">
            <n-card size="small" :bordered="false">
              <n-thing :title="profileTitle" :description="profileDescription">
                <template #avatar>
                  <n-avatar :size="44" round>
                    <n-icon :component="PersonOutline" :size="22" />
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

            <n-card size="small" title="本地数据" :bordered="false" segmented>
              <n-list>
                <n-list-item>
                  <n-thing
                    title="收藏场次"
                    :description="`共 ${favoriteCount} 场 · 今日 ${todayFavoriteCount} 场`"
                  >
                    <template #avatar>
                      <n-icon :component="StarOutline" :size="20" />
                    </template>
                    <template #header-extra>
                      <n-button size="small" secondary type="warning" @click="goFavorites">
                        查看
                      </n-button>
                    </template>
                  </n-thing>
                </n-list-item>
              </n-list>
            </n-card>

            <n-card size="small" title="账号与偏好" :bordered="false" segmented>
              <n-list>
                <n-list-item v-if="!isLoggedIn">
                  <template #prefix>
                    <n-icon :component="LogInOutline" :size="20" />
                  </template>
                  <n-thing
                    title="登录账号"
                    description="打开登录表单；桌面端登录后才显示「我的」入口"
                  />
                  <template #suffix>
                    <n-button size="small" type="primary" @click="openLogin">
                      登录
                    </n-button>
                  </template>
                </n-list-item>
                <n-list-item>
                  <template #prefix>
                    <n-icon :component="isDark ? MoonOutline : SunnyOutline" :size="20" />
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
                <n-list-item v-if="isLoggedIn">
                  <template #prefix>
                    <n-icon :component="LogOutOutline" :size="20" />
                  </template>
                  <n-thing
                    title="退出登录"
                    :description="
                      isPhone
                        ? '退出后仍可继续使用本地功能'
                        : '退出后桌面端「我的」入口会隐藏'
                    "
                  />
                  <template #suffix>
                    <n-button size="small" @click="onLogout">退出</n-button>
                  </template>
                </n-list-item>
              </n-list>
            </n-card>

            <n-card size="small" title="关于" :bordered="false" segmented>
              <template #header-extra>
                <n-icon :component="InformationCircleOutline" :size="16" />
              </template>
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
                  手机「我的」内可登录；桌面未登录时顶栏显示「登录」
                </n-descriptions-item>
              </n-descriptions>
            </n-card>
          </n-space>
        </div>
      </n-scrollbar>
    </div>
  </div>
</template>

<style scoped>
.mine-shell {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.mine-body {
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
  box-sizing: border-box;
}
</style>
