<script setup lang="ts">
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineVipMembers' })
</script>

<template>
  <MineSectionBody>
    <n-card size="small" title="会员管理" :bordered="false">
      <n-alert type="info" :bordered="false">
        VIP 权益与发卡能力尚在规划中（见仓库 <code>docs/AUTH_VIP_QUOTA.md</code>）。
        落地后可在此查询账号、授予或调整 VIP 档位与到期时间。
      </n-alert>
    </n-card>
  </MineSectionBody>
</template>
