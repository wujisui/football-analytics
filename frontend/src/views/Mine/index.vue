<script setup lang="ts">
defineOptions({ name: 'Mine' })
</script>

<template>
  <div class="mine-page fa-page-frame">
    <div class="mine-card">
      <n-empty description="登录功能即将开放">
        <template #extra>
          <n-text depth="3" class="mine-hint">账号与个人中心预留入口</n-text>
        </template>
      </n-empty>
    </div>
  </div>
</template>

<style scoped>
.mine-page {
  height: 100%;
  box-sizing: border-box;
  padding: var(--fa-content-block-start) var(--fa-content-inline) var(--fa-content-block-end);
  display: flex;
  flex-direction: column;
}

.mine-card {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--fa-bg-elevated);
  border: 1px solid var(--fa-border);
  border-radius: 8px;
}

.mine-hint {
  font-size: 12px;
}
</style>
