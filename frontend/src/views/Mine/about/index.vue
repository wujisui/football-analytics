<script setup lang="ts">
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'
import pkg from '../../../../package.json'

defineOptions({ name: 'MineAbout' })
</script>

<template>
  <MineSectionBody>
    <n-card size="small" :bordered="false">
      <n-descriptions
        label-placement="left"
        :column="1"
        size="small"
        :label-style="{ width: '72px' }"
      >
        <n-descriptions-item label="定位">
          赛前分析工具，非实时比分站
        </n-descriptions-item>
        <n-descriptions-item label="版本">
          {{ pkg.version }}
        </n-descriptions-item>
        <n-descriptions-item label="数据">
          仅调用本项目后端；官方 Key 不进入前端
        </n-descriptions-item>
        <n-descriptions-item label="账号">
          未登录也可进入“我的”；登录后在个人主页查看账号信息
        </n-descriptions-item>
      </n-descriptions>
    </n-card>
  </MineSectionBody>
</template>
