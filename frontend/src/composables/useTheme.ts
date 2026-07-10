import { darkTheme, type GlobalTheme, type GlobalThemeOverrides } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import {
  THEME_OPTIONS,
  applyShellCssVars,
  getPreset,
  type ThemePresetId,
} from '@/theme/presets'

const STORAGE_KEY = 'fa-theme-preset'

function readStored(): ThemePresetId {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v && THEME_OPTIONS.some((o) => o.value === v)) {
      return v as ThemePresetId
    }
    // migrate old light/dark toggle
    if (v === 'dark') return 'dark'
    if (v === 'light') return 'light'
  } catch {
    /* ignore */
  }
  return 'light'
}

const presetId = ref<ThemePresetId>(readStored())

watch(
  presetId,
  (id) => {
    const preset = getPreset(id)
    try {
      localStorage.setItem(STORAGE_KEY, id)
    } catch {
      /* ignore */
    }
    applyShellCssVars(preset)
  },
  { immediate: true },
)

export function useTheme() {
  const preset = computed(() => getPreset(presetId.value))

  const naiveTheme = computed<GlobalTheme | null>(() =>
    preset.value.dark ? darkTheme : null,
  )

  const themeOverrides = computed<GlobalThemeOverrides>(
    () => preset.value.overrides,
  )

  function setPreset(id: ThemePresetId) {
    presetId.value = id
  }

  return {
    presetId,
    preset,
    naiveTheme,
    themeOverrides,
    themeOptions: THEME_OPTIONS,
    isDark: computed(() => preset.value.dark),
    setPreset,
  }
}
