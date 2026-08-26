<script setup lang="ts">
import { MoonOutline, SunnyOutline } from '@vicons/ionicons5'

import HandicapRulesetSwitch from '@/components/HandicapRulesetSwitch.vue'
import TextSwitch from '@/components/TextSwitch.vue'
import { useTheme } from '@/composables/useTheme'
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineTheme' })

const { isDark, toggleTheme } = useTheme()
</script>

<template>
  <MineSectionBody>
    <n-flex vertical :size="12">
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
              description="偏好保存在本机，下次打开沿用"
            />
            <template #suffix>
              <TextSwitch
                :value="isDark"
                checked-text="深色"
                unchecked-text="浅色"
                aria-label="深色模式"
                @update:value="toggleTheme"
              />
            </template>
          </n-list-item>
        </n-list>
      </n-card>

      <n-card size="small" title="让球玩法" :bordered="false">
        <n-list>
          <n-list-item>
            <n-thing
              title="当前口径"
              description="偏好保存在本机，切换后立即更新展示与结算"
            />
            <template #suffix>
              <HandicapRulesetSwitch />
            </template>
          </n-list-item>
          <n-list-item>
            <n-thing
              title="结算口径"
              description="只对让球胜平负生效。亚盘：让胜 / 让负，整数盘打成让球平走水，四分盘出赢半 / 输半。竞彩：盘口按绝对值向上取整成整数（-0.5 → -1）后判让胜 / 让平 / 让负，不出半结果。大小球、双进等其余玩法一律按亚盘拆盘。只改展示与结算，不回写已保存方案和冻结预测。"
            />
          </n-list-item>
        </n-list>
      </n-card>
    </n-flex>
  </MineSectionBody>
</template>
