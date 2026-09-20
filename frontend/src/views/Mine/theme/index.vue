<script setup lang="ts">
import { EyeOutline, MoonOutline, SunnyOutline } from '@vicons/ionicons5'
import { computed } from 'vue'

import { useTheme } from '@/composables/useTheme'
import { THEME_PRESETS, type ThemePresetId } from '@/theme/presets'
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineTheme' })

const { presetId, setPreset } = useTheme()

const themeOptions = THEME_PRESETS.map(({ id, label }) => ({
  label,
  value: id,
}))

const themeIcon = computed(() => {
  if (presetId.value === 'dark') return MoonOutline
  if (presetId.value === 'eye-care') return EyeOutline
  return SunnyOutline
})

function onThemeChange(value: ThemePresetId) {
  setPreset(value)
}
</script>

<template>
  <MineSectionBody>
    <n-flex vertical :size="12">
      <n-card
        size="small"
        title="主题"
        :bordered="false"
        :segmented="{ content: true }"
      >
        <n-list>
          <n-list-item>
            <template #prefix>
              <n-icon
                :component="themeIcon"
                :size="20"
              />
            </template>
            <n-thing
              title="界面主题"
              description="偏好保存在本机，下次打开沿用"
            />
            <template #suffix>
              <n-select
                :value="presetId"
                :options="themeOptions"
                aria-label="界面主题"
                style="width: 112px"
                @update:value="onThemeChange"
              />
            </template>
          </n-list-item>
        </n-list>
      </n-card>

      <n-card
        size="small"
        title="让球玩法"
        :bordered="false"
        :segmented="{ content: true }"
      >
        <n-list>
          <n-list-item>
            <n-thing
              title="结算口径"
              description="让球只按亚盘结算：让胜 / 让负两路，整数盘打成让球平走水，四分盘出赢半 / 输半，没有让球平这一注。大小球、双进同样按亚盘拆盘。"
            />
          </n-list-item>
        </n-list>
      </n-card>
    </n-flex>
  </MineSectionBody>
</template>
