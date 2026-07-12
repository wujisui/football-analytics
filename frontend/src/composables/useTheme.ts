import { darkTheme, type GlobalTheme, type GlobalThemeOverrides } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import {
  applyShellCssVars,
  getPreset,
  normalizePresetId,
  type ThemePresetId,
} from '@/theme/presets'

const STORAGE_KEY = 'fa-theme-preset'

function readStored(): ThemePresetId {
  try {
    return normalizePresetId(localStorage.getItem(STORAGE_KEY))
  } catch {
    return 'light'
  }
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

  const isDark = computed(() => preset.value.dark)

  function setPreset(id: ThemePresetId) {
    presetId.value = id
  }

  function toggleTheme() {
    presetId.value = isDark.value ? 'light' : 'dark'
  }

  return {
    presetId,
    preset,
    naiveTheme,
    themeOverrides,
    isDark,
    setPreset,
    toggleTheme,
  }
}
