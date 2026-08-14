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
  admin: {
    routeName: 'mine-admin',
    title: '管理员设置',
    description: '管理定时同步与数据获取开关',
    icon: SettingsOutline,
  },
  about: {
    routeName: 'mine-about',
    title: '关于',
    description: 'Football Analytics 产品说明与版本信息',
    icon: InformationCircleOutline,
  },
}

export function sectionFromRouteName(name: unknown): MineSection {
  const matched = Object.entries(sectionMeta).find(
    ([, meta]) => meta.routeName === name,
  )
  return (matched?.[0] as MineSection | undefined) ?? 'account'
}
