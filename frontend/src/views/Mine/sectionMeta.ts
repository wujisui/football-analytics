import {
  BookmarkOutline,
  ColorPaletteOutline,
  ConstructOutline,
  DocumentTextOutline,
  InformationCircleOutline,
  PeopleOutline,
  PersonOutline,
  ServerOutline,
  TrophyOutline,
} from '@vicons/ionicons5'
import type { Component } from 'vue'

export type MineSection =
  | 'account'
  | 'plans'
  | 'theme'
  | 'hotLeagues'
  | 'adminOps'
  | 'adminBackend'
  | 'vipMembers'
  | 'vipRecords'
  | 'about'

export const sectionMeta: Record<
  MineSection,
  { routeName: string; title: string; icon: Component; hint?: string }
> = {
  account: {
    routeName: 'mine-account',
    title: '个人主页',
    hint: '查看当前账号状态与基础信息',
    icon: PersonOutline,
  },
  plans: {
    // PC 顶栏第二行显示当天方案统计 + 日期选择，不用说明文案
    routeName: 'mine-plans',
    title: '我的方案',
    icon: BookmarkOutline,
  },
  theme: {
    routeName: 'mine-theme',
    title: '偏好设置',
    hint: '显示主题与让球结算口径',
    icon: ColorPaletteOutline,
  },
  hotLeagues: {
    routeName: 'mine-hot-leagues',
    title: '热门联赛',
    hint: '勾选进侧栏「热门」并定时拉赛前盘口；未勾选进「其他」，只入库赛程',
    icon: TrophyOutline,
  },
  adminOps: {
    routeName: 'mine-admin-ops',
    title: '运维管理',
    hint: '同步数据、更新赛果、订阅与全天密刷调度',
    icon: ConstructOutline,
  },
  adminBackend: {
    routeName: 'mine-admin-backend',
    title: '后台管理',
    hint: '官方 Key 与比赛历史清空等高危操作',
    icon: ServerOutline,
  },
  vipMembers: {
    routeName: 'mine-vip-members',
    title: '会员管理',
    hint: '查询账号并授予或调整 VIP 权益',
    icon: PeopleOutline,
  },
  vipRecords: {
    routeName: 'mine-vip-records',
    title: '订阅记录',
    hint: 'VIP 开通、续费与到期流水',
    icon: DocumentTextOutline,
  },
  about: {
    routeName: 'mine-about',
    title: '关于',
    hint: 'Football Analytics 产品说明与版本信息',
    icon: InformationCircleOutline,
  },
}

/** Admin-only sections: redirect non-admins away from these routes. */
export const adminOnlySections = new Set<MineSection>([
  'hotLeagues',
  'adminOps',
  'adminBackend',
  'vipMembers',
  'vipRecords',
])

export function isAdminOnlySection(section: string): boolean {
  return adminOnlySections.has(section as MineSection)
}

export function sectionFromRouteName(name: unknown): MineSection {
  const matched = Object.entries(sectionMeta).find(
    ([, meta]) => meta.routeName === name,
  )
  return (matched?.[0] as MineSection | undefined) ?? 'account'
}

const LAST_MINE_ROUTE_KEY = 'fa-mine-last-route'

export function isMineRouteName(name: unknown): boolean {
  return String(name ?? '').startsWith('mine')
}

/** Remember the subsection left when navigating off 【我的】. */
export function rememberLastMineRoute(name: unknown): void {
  if (!isMineRouteName(name)) return
  try {
    sessionStorage.setItem(LAST_MINE_ROUTE_KEY, String(name))
  } catch {
    /* private mode / quota */
  }
}

/** PC top-nav restore target; admin-only pages fall back for non-admins. */
export function restoredMineRouteName(isAdmin: boolean): string {
  try {
    const raw = sessionStorage.getItem(LAST_MINE_ROUTE_KEY)
    if (!raw) return sectionMeta.account.routeName
    const section = sectionFromRouteName(raw)
    if (sectionMeta[section].routeName !== raw) return sectionMeta.account.routeName
    if (isAdminOnlySection(section) && !isAdmin) return sectionMeta.account.routeName
    return raw
  } catch {
    return sectionMeta.account.routeName
  }
}

export function clearLastMineRoute(): void {
  try {
    sessionStorage.removeItem(LAST_MINE_ROUTE_KEY)
  } catch {
    /* ignore */
  }
}
