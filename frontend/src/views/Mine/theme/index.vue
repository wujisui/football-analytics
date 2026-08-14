<script setup lang="ts">
import { MoonOutline, SunnyOutline } from '@vicons/ionicons5'

import { useTheme } from '@/composables/useTheme'
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineTheme' })

const { isDark, toggleTheme } = useTheme()
</script>

<template>
  <MineSectionBody>
    <n-card size="small" title="主题" :bordered="false">
      <n-list>
        <n-list-item>
          <template #prefix>
            <n-icon
              :component="isDark ? MoonOutline : SunnyOutline"
              :size="20"
            />
          </template>
          <n-thing
            title="深色模式"
            description="与顶栏主题开关同步，偏好保存在本机"
          />
          <template #suffix>
            <n-switch
              :value="isDark"
              aria-label="深色模式"
              @update:value="toggleTheme"
            />
          </template>
        </n-list-item>
      </n-list>
    </n-card>
  </MineSectionBody>
</template>
