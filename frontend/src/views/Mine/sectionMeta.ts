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
    hint: '同步官方数据、赛果回写、订阅与早间盘口调度',
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
