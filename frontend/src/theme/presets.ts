import type { GlobalThemeOverrides } from 'naive-ui'

export type ThemePresetId =
  | 'light'
  | 'dark'
  | 'light-blue'
  | 'light-orange'
  | 'dark-blue'
  | 'dark-orange'

export interface ThemePreset {
  id: ThemePresetId
  label: string
  /** Whether Naive `darkTheme` is applied */
  dark: boolean
  /** Naive theme-overrides (library-native customization) */
  overrides: GlobalThemeOverrides
  /** Page shell tokens for custom (non-Naive) surfaces */
  shell: {
    bg: string
    bgElevated: string
    bgSoft: string
    border: string
    borderSoft: string
    text: string
    textStrong: string
    textSecondary: string
    textMuted: string
    textFaint: string
    hoverBorder: string
    hoverShadow: string
    highlightBg: string
    highlightBorder: string
    highlightText: string
  }
}

const lightShell = {
  bg: '#f5f6f8',
  bgElevated: '#ffffff',
  bgSoft: '#fafafa',
  border: '#e8e8e8',
  borderSoft: '#f0f0f0',
  text: '#213547',
  textStrong: '#1a1a1a',
  textSecondary: '#666666',
  textMuted: '#888888',
  textFaint: '#999999',
  hoverBorder: '#b8d4f8',
  hoverShadow: 'rgba(32, 128, 240, 0.08)',
  highlightBg: '#fff7e6',
  highlightBorder: '#f0c78a',
  highlightText: '#c2410c',
} as const

const darkShell = {
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
  highlightBg: 'rgba(240, 160, 32, 0.12)',
  highlightBorder: '#8a6a2b',
  highlightText: '#f0c78a',
} as const

function primaryOverrides(
  primary: string,
  hover: string,
  pressed: string,
  suppl: string,
): GlobalThemeOverrides {
  return {
    common: {
      primaryColor: primary,
      primaryColorHover: hover,
      primaryColorPressed: pressed,
      primaryColorSuppl: suppl,
    },
  }
}

/**
 * Presets:
 * - `light` / `dark`: Naive UI built-in themes only (theme=null / darkTheme, no overrides)
 * - others: same base + theme-overrides for primary color
 */
export const THEME_PRESETS: ThemePreset[] = [
  {
    id: 'light',
    label: '浅色（Naive 默认）',
    dark: false,
    overrides: {},
    shell: lightShell,
  },
  {
    id: 'dark',
    label: '深色（Naive 默认）',
    dark: true,
    overrides: {},
    shell: darkShell,
  },
  {
    id: 'light-blue',
    label: '浅色 · 蓝色',
    dark: false,
    overrides: primaryOverrides('#2080f0', '#4098fc', '#1060c9', '#2080f0'),
    shell: lightShell,
  },
  {
    id: 'light-orange',
    label: '浅色 · 橙色',
    dark: false,
    overrides: primaryOverrides('#f0a020', '#fcb040', '#c97c10', '#f0a020'),
    shell: lightShell,
  },
  {
    id: 'dark-blue',
    label: '深色 · 蓝色',
    dark: true,
    overrides: primaryOverrides('#70c0e8', '#8acbec', '#5a9fc7', '#70c0e8'),
    shell: darkShell,
  },
  {
    id: 'dark-orange',
    label: '深色 · 橙色',
    dark: true,
    overrides: primaryOverrides('#fcb040', '#ffc860', '#d09020', '#fcb040'),
    shell: darkShell,
  },
]

export const THEME_OPTIONS = THEME_PRESETS.map((p) => ({
  label: p.label,
  value: p.id,
}))

export function getPreset(id: string | null | undefined): ThemePreset {
  return THEME_PRESETS.find((p) => p.id === id) ?? THEME_PRESETS[0]
}

export function applyShellCssVars(preset: ThemePreset) {
  const root = document.documentElement
  const s = preset.shell
  root.dataset.theme = preset.dark ? 'dark' : 'light'
  root.style.setProperty('--fa-bg', s.bg)
  root.style.setProperty('--fa-bg-elevated', s.bgElevated)
  root.style.setProperty('--fa-bg-soft', s.bgSoft)
  root.style.setProperty('--fa-border', s.border)
  root.style.setProperty('--fa-border-soft', s.borderSoft)
  root.style.setProperty('--fa-text', s.text)
  root.style.setProperty('--fa-text-strong', s.textStrong)
  root.style.setProperty('--fa-text-secondary', s.textSecondary)
  root.style.setProperty('--fa-text-muted', s.textMuted)
  root.style.setProperty('--fa-text-faint', s.textFaint)
  root.style.setProperty('--fa-hover-border', s.hoverBorder)
  root.style.setProperty('--fa-hover-shadow', s.hoverShadow)
  root.style.setProperty('--fa-highlight-bg', s.highlightBg)
  root.style.setProperty('--fa-highlight-border', s.highlightBorder)
  root.style.setProperty('--fa-highlight-text', s.highlightText)
}
