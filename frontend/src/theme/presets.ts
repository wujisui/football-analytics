import type { GlobalThemeOverrides } from 'naive-ui'

/** Restored stock light, dark, and the warm paper-grey eye-care theme. */
export type ThemePresetId = 'light' | 'dark' | 'eye-care'

export const DEFAULT_THEME: ThemePresetId = 'eye-care'

export const THEME_STORAGE_KEY = 'fa-theme-preset-v2'
export const THEME_LEGACY_STORAGE_KEY = 'fa-theme-preset'

const LEGACY_INLINE_VARS = [
  '--fa-bg',
  '--fa-backdrop',
  '--fa-bg-elevated',
  '--fa-bg-soft',
  '--fa-border',
  '--fa-border-soft',
  '--fa-text',
  '--fa-text-strong',
  '--fa-text-secondary',
  '--fa-text-muted',
  '--fa-text-faint',
  '--fa-hover-border',
  '--fa-hover-shadow',
  '--fa-accent',
  '--fa-highlight-bg',
  '--fa-highlight-border',
  '--fa-highlight-text',
  '--fa-header-shadow',
  '--fa-bottom-nav-shadow',
  '--fa-sider-shadow',
] as const

export interface ThemePreset {
  id: ThemePresetId
  label: string
  /** Whether Naive `darkTheme` is applied */
  dark: boolean
  /** Naive theme-overrides (empty for stock themes) */
  overrides: GlobalThemeOverrides
}

const eyeCareOverrides: GlobalThemeOverrides = {
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

/** Theme selector options in product display order. */
export const THEME_PRESETS: ThemePreset[] = [
  {
    id: 'dark',
    label: '深色',
    dark: true,
    overrides: {},
  },
  {
    id: 'light',
    label: '浅色',
    dark: false,
    overrides: {},
  },
  {
    id: 'eye-care',
    label: '护眼',
    dark: false,
    overrides: eyeCareOverrides,
  },
]

/** Normalize current and legacy color-variant ids. */
export function normalizePresetId(id: string | null | undefined): ThemePresetId {
  if (!id) return DEFAULT_THEME
  if (id === 'eye-care') return 'eye-care'
  if (id === 'dark' || id.startsWith('dark-')) return 'dark'
  if (id === 'light' || id.startsWith('light-')) return 'light'
  return DEFAULT_THEME
}

export function getPreset(id: string | null | undefined): ThemePreset {
  const normalized = normalizePresetId(id)
  return (
    THEME_PRESETS.find((p) => p.id === normalized) ??
    THEME_PRESETS.find((p) => p.id === DEFAULT_THEME)!
  )
}

/** Switch CSS by `html[data-theme]`. Palette lives in `src/styles/themes/`. */
export function applyThemeAttribute(preset: ThemePreset) {
  const root = document.documentElement
  root.dataset.theme = preset.id
  for (const name of LEGACY_INLINE_VARS) {
    root.style.removeProperty(name)
  }
}
