import type { GlobalThemeOverrides } from 'naive-ui'

/** Single light/dark choice; light uses a warm paper-grey surface palette. */
export type ThemePresetId = 'light' | 'dark'

export const DEFAULT_THEME: ThemePresetId = 'light'

const SHELL_CSS_KEYS = [
  'bg',
  'bgElevated',
  'bgSoft',
  'border',
  'borderSoft',
  'text',
  'textStrong',
  'textSecondary',
  'textMuted',
  'textFaint',
  'hoverBorder',
  'hoverShadow',
  'accent',
  'highlightBg',
  'highlightBorder',
  'highlightText',
] as const

type ShellToken = (typeof SHELL_CSS_KEYS)[number]

export interface ThemePreset {
  id: ThemePresetId
  label: string
  /** Whether Naive `darkTheme` is applied */
  dark: boolean
  /** Naive theme-overrides (empty for stock themes) */
  overrides: GlobalThemeOverrides
  /** Page shell tokens for custom (non-Naive) surfaces */
  shell: Record<ShellToken, string>
}

const SHELL_CSS_VARS: Record<ShellToken, string> = {
  bg: '--fa-bg',
  bgElevated: '--fa-bg-elevated',
  bgSoft: '--fa-bg-soft',
  border: '--fa-border',
  borderSoft: '--fa-border-soft',
  text: '--fa-text',
  textStrong: '--fa-text-strong',
  textSecondary: '--fa-text-secondary',
  textMuted: '--fa-text-muted',
  textFaint: '--fa-text-faint',
  hoverBorder: '--fa-hover-border',
  hoverShadow: '--fa-hover-shadow',
  accent: '--fa-accent',
  highlightBg: '--fa-highlight-bg',
  highlightBorder: '--fa-highlight-border',
  highlightText: '--fa-highlight-text',
}

const lightShell: ThemePreset['shell'] = {
  bg: '#e1dbd3',
  bgElevated: '#f3f0eb',
  bgSoft: '#e9e4dc',
  border: '#d0c9c0',
  borderSoft: '#ded8d0',
  text: '#3a352f',
  textStrong: '#262220',
  textSecondary: '#6b6359',
  textMuted: '#857d72',
  textFaint: '#9c9489',
  hoverBorder: '#9fc1ea',
  hoverShadow: 'rgba(74, 62, 48, 0.12)',
  accent: '#2080f0',
  highlightBg: '#f7e9d1',
  highlightBorder: '#eac388',
  highlightText: '#c2410c',
}

const lightOverrides: GlobalThemeOverrides = {
  common: {
    bodyColor: '#e1dbd3',
    baseColor: '#f3f0eb',
    cardColor: '#f3f0eb',
    modalColor: '#f3f0eb',
    popoverColor: '#f3f0eb',
    tableColor: '#f3f0eb',
    tableHeaderColor: '#eae5dd',
    inputColor: '#ebe6de',
    inputColorDisabled: '#e4ded5',
    actionColor: '#eae5dd',
    tagColor: '#eae5dd',
    tabColor: '#eae5dd',
    codeColor: '#eae5dd',
    hoverColor: '#e6e0d7',
    borderColor: '#d0c9c0',
    dividerColor: '#ddd6cd',
    textColorBase: '#3a352f',
    textColor1: '#262220',
    textColor2: '#3a352f',
    textColor3: '#6b6359',
    textColorDisabled: '#aaa298',
    placeholderColor: '#948b80',
    placeholderColorDisabled: '#bab2a8',
    boxShadow1: '0 1px 4px rgba(74, 62, 48, 0.08)',
    boxShadow2: '0 4px 14px rgba(74, 62, 48, 0.1)',
    boxShadow3: '0 8px 24px rgba(74, 62, 48, 0.12)',
  },
}

const darkShell: ThemePreset['shell'] = {
  bg: '#101014',
  bgElevated: '#18181c',
  bgSoft: '#1f1f24',
  border: '#2e2e36',
  borderSoft: '#2a2a30',
  text: '#e5e5e5',
  textStrong: '#f5f5f5',
  textSecondary: '#a3a3a3',
  textMuted: '#8b8b8b',
  textFaint: '#737373',
  hoverBorder: '#3b6ea8',
  hoverShadow: 'rgba(0, 0, 0, 0.35)',
  accent: '#69b1ff',
  highlightBg: 'rgba(240, 160, 32, 0.12)',
  highlightBorder: '#8a6a2b',
  highlightText: '#f0c78a',
}

/** One softened neutral light theme and Naive's dark theme. */
export const THEME_PRESETS: ThemePreset[] = [
  {
    id: 'light',
    label: '浅色',
    dark: false,
    overrides: lightOverrides,
    shell: lightShell,
  },
  {
    id: 'dark',
    label: '深色',
    dark: true,
    overrides: {},
    shell: darkShell,
  },
]

/** Map legacy color-variant ids → light/dark. Missing → light default. */
export function normalizePresetId(id: string | null | undefined): ThemePresetId {
  if (!id) return DEFAULT_THEME
  if (id === 'dark' || id.startsWith('dark-')) return 'dark'
  if (id === 'light' || id.startsWith('light-')) return 'light'
  return DEFAULT_THEME
}

export function getPreset(id: string | null | undefined): ThemePreset {
  const normalized = normalizePresetId(id)
  return THEME_PRESETS.find((p) => p.id === normalized) ?? THEME_PRESETS[0]
}

export function applyShellCssVars(preset: ThemePreset) {
  const root = document.documentElement
  root.dataset.theme = preset.dark ? 'dark' : 'light'
  for (const key of SHELL_CSS_KEYS) {
    root.style.setProperty(SHELL_CSS_VARS[key], preset.shell[key])
  }
}
