import type { GlobalThemeOverrides } from 'naive-ui'

/** Only Naive built-in light / dark (no color variants). */
export type ThemePresetId = 'light' | 'dark'

export const DEFAULT_THEME: ThemePresetId = 'dark'

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
  highlightBg: '--fa-highlight-bg',
  highlightBorder: '--fa-highlight-border',
  highlightText: '--fa-highlight-text',
}

const lightShell: ThemePreset['shell'] = {
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
  highlightBg: 'rgba(240, 160, 32, 0.12)',
  highlightBorder: '#8a6a2b',
  highlightText: '#f0c78a',
}

/** Official themes only: `light` (Naive default) / `dark` (Naive `darkTheme`). */
export const THEME_PRESETS: ThemePreset[] = [
  {
    id: 'dark',
    label: '深色',
    dark: true,
    overrides: {},
    shell: darkShell,
  },
  {
    id: 'light',
    label: '浅色',
    dark: false,
    overrides: {},
    shell: lightShell,
  },
]

/** Map legacy color-variant ids → light/dark. Missing → dark default. */
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
