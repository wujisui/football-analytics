<template>
  <n-scrollbar class="mine-content-scroll" trigger="hover">
    <div class="mine-content">
      <slot />
    </div>
  </n-scrollbar>
</template>

<style scoped>
.mine-content-scroll {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.mine-content {
  width: 100%;
  padding: var(--fa-content-block-start) var(--fa-content-inline)
    var(--fa-content-block-end);
  box-sizing: border-box;
}

.mine-content > * + * {
  margin-top: 14px;
}

@media (max-width: 767px) {
  .mine-content {
    padding: 14px var(--fa-content-inline) 24px;
  }
}
</style>
