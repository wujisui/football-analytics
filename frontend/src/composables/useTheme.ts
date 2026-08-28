import { darkTheme, type GlobalTheme, type GlobalThemeOverrides } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import {
  applyThemeAttribute,
  DEFAULT_THEME,
  getPreset,
  normalizePresetId,
  THEME_LEGACY_STORAGE_KEY,
  THEME_STORAGE_KEY,
  type ThemePresetId,
} from '@/theme/presets'

function readStored(): ThemePresetId {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    if (stored) return normalizePresetId(stored)

    // Before the three-theme selector, the warm eye-care palette was stored as
    // "light". Preserve that visual preference; a real dark choice stays dark.
    const legacy = localStorage.getItem(THEME_LEGACY_STORAGE_KEY)
    return legacy && normalizePresetId(legacy) === 'dark' ? 'dark' : DEFAULT_THEME
  } catch {
    return DEFAULT_THEME
  }
}

const presetId = ref<ThemePresetId>(readStored())

watch(
  presetId,
  (id) => {
    const preset = getPreset(id)
    try {
      localStorage.setItem(THEME_STORAGE_KEY, id)
    } catch {
      /* ignore */
    }
    applyThemeAttribute(preset)
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
    naiveTheme,
    themeOverrides,
    presetId,
    setPreset,
  }
}
