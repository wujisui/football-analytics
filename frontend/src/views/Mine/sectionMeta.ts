import {
  BookmarkOutline,
  ColorPaletteOutline,
  InformationCircleOutline,
  PersonOutline,
  SettingsOutline,
  TrophyOutline,
} from '@vicons/ionicons5'
import type { Component } from 'vue'

export type MineSection =
  | 'account'
  | 'plans'
  | 'theme'
  | 'hotLeagues'
  | 'admin'
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
    title: '主题与玩法',
    hint: '显示主题与让球结算口径',
    icon: ColorPaletteOutline,
  },
  hotLeagues: {
    routeName: 'mine-hot-leagues',
    title: '热门联赛',
    hint: '勾选进侧栏「热门」并定时拉赛前盘口；未勾选进「其他」，只入库赛程',
    icon: TrophyOutline,
  },
  admin: {
    routeName: 'mine-admin',
    title: '管理员设置',
    hint: '订阅状态决定完整批次、盘口频率与详情获取范围',
    icon: SettingsOutline,
  },
  about: {
    routeName: 'mine-about',
    title: '关于',
    hint: 'Football Analytics 产品说明与版本信息',
    icon: InformationCircleOutline,
  },
}

export function sectionFromRouteName(name: unknown): MineSection {
  const matched = Object.entries(sectionMeta).find(
    ([, meta]) => meta.routeName === name,
  )
  return (matched?.[0] as MineSection | undefined) ?? 'account'
}
