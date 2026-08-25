<script setup lang="ts">
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineVipRecords' })
</script>

<template>
  <MineSectionBody>
    <n-card size="small" title="订阅记录" :bordered="false">
      <n-alert type="info" :bordered="false">
        用户 VIP 订阅与支付流水尚未接入。支付渠道落地后，将在此展示开通、续费、到期与来源（支付 / 管理员发卡）。
      </n-alert>
    </n-card>
  </MineSectionBody>
</template>
