<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import BasicInfo from '@/views/Detail/components/BasicInfo.vue'
import TabsContainer from '@/views/Detail/components/TabsContainer.vue'
import { useFixtureAnalysis } from '@/views/Detail/composables/useFixtureAnalysis'
import { useIsPhone } from '@/composables/useMediaQuery'
import { parseDetailTab, peekDetailCrumb, type DetailTab } from '@/utils/detailNav'

const props = defineProps<{
  fixtureId: string
}>()

const route = useRoute()
const router = useRouter()
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
const contentLoading = computed(() => loading.value || !data.value)

/** Breadcrumb is list-known chrome — never wait on /analysis skeleton. */
const crumbFixture = computed(
  () => data.value ?? peekDetailCrumb(fixtureIdNumber.value),
)

const initialTab = computed(() => parseDetailTab(route.query.tab))

/** Mirror the open tab into the URL so a reload lands on the same pane. */
function onTabChange(tab: DetailTab) {
  if (route.query.tab === tab) return
  void router.replace({
    name: 'fixture-detail',
    params: { fixtureId: props.fixtureId },
    query: { ...route.query, tab },
  })
}

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
  <div class="fa-page-frame">
  <n-layout class="detail-layout fa-page-shell">
    <n-layout-content
      class="detail-content"
      :native-scrollbar="false"
      :content-style="contentStyle"
    >
      <div class="detail-body">
        <BasicInfo :fixture="crumbFixture" />

        <TabsContainer
          class="tabs-fill"
          :fixture="data"
          :pkg="data?.analysis.package ?? null"
          :loading="contentLoading"
          :error="error"
          :initial-tab="initialTab"
          @retry="reload"
          @tab-change="onTabChange"
        />
      </div>
    </n-layout-content>
  </n-layout>
  </div>
</template>

<style scoped>
.detail-layout {
  height: 100%;
  background: var(--fa-bg);
}

.detail-content {
  height: 100%;
}

.detail-body {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
  padding-bottom: env(safe-area-inset-bottom, 0px);
}

.detail-body :deep(.basic-info) {
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
  .detail-body {
    gap: 16px;
  }
}
</style>
