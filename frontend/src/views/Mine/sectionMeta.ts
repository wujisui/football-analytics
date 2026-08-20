import {
  BookmarkOutline,
  ColorPaletteOutline,
  InformationCircleOutline,
  PersonOutline,
  SettingsOutline,
} from '@vicons/ionicons5'
import type { Component } from 'vue'

export type MineSection = 'account' | 'plans' | 'theme' | 'admin' | 'about'

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
  admin: {
    routeName: 'mine-admin',
    title: '管理员设置',
    hint: '管理定时同步与数据获取开关',
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
