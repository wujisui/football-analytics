<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'

import BasicInfo from '@/components/detail/BasicInfo.vue'
import TabsContainer from '@/components/detail/TabsContainer.vue'
import { useFixtureAnalysis } from '@/composables/useFixtureAnalysis'
import { useIsPhone } from '@/composables/useMediaQuery'

const props = defineProps<{
  fixtureId: string
}>()

const isPhone = useIsPhone()
const contentStyle = computed(
  () =>
    `height: 100%; box-sizing: border-box; padding: ${
      isPhone.value ? '12px 12px 16px' : '16px 20px 24px'
    }; display: flex; flex-direction: column; overflow: hidden;`,
)

const fixtureIdNumber = computed(() => Number(props.fixtureId))
const { data, loading, error, ensureLoaded, reload, reset } =
  useFixtureAnalysis(fixtureIdNumber)

onMounted(() => {
  void ensureLoaded()
})

watch(
  () => props.fixtureId,
  () => {
    reset()
    void ensureLoaded()
  },
)
</script>

<template>
  <n-layout class="detail-layout" position="absolute">
    <n-layout-content
      class="detail-content"
      :native-scrollbar="false"
      :content-style="contentStyle"
    >
      <n-spin class="detail-spin" :show="loading && !data">
        <div class="spin-body">
          <n-alert v-if="error && !data" type="error" :title="error">
            <n-button size="small" type="primary" :loading="loading" @click="reload">
              重试
            </n-button>
          </n-alert>

          <template v-else-if="data">
            <BasicInfo :fixture="data" />
            <TabsContainer
              class="tabs-fill"
              :fixture="data"
              :pkg="data.analysis.package ?? null"
              :loading="loading"
              :error="error"
              @retry="reload"
            />
          </template>
        </div>
      </n-spin>
    </n-layout-content>
  </n-layout>
</template>

<style scoped>
.detail-layout {
  inset: 0;
  height: 100%;
  background: var(--fa-bg);
}

.detail-content {
  height: 100%;
}

.detail-spin {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-spin :deep(.n-spin-container),
.detail-spin :deep(.n-spin-body),
.detail-spin :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.spin-body {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  max-width: 1520px;
  margin: 0 auto;
  box-sizing: border-box;
  overflow: hidden;
  padding-bottom: env(safe-area-inset-bottom, 0px);
}

.spin-body :deep(.basic-info) {
  flex-shrink: 0;
}

.tabs-fill {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

@media (min-width: 1024px) {
  .spin-body {
    gap: 16px;
  }
}
</style>
