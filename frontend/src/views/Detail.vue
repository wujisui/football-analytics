<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import BasicInfo from '@/components/detail/BasicInfo.vue'
import TabsContainer from '@/components/detail/TabsContainer.vue'
import { useFixtureAnalysis } from '@/composables/useFixtureAnalysis'
import { useIsPhone } from '@/composables/useMediaQuery'
import {
  detailBackRoute,
  detailRootLabel,
  parseDetailFrom,
  parseDetailTab,
} from '@/utils/detailNav'

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

const from = computed(() => parseDetailFrom(route.query.from))
const rootLabel = computed(() => detailRootLabel(from.value))
const fromDate = computed(() =>
  typeof route.query.date === 'string' ? route.query.date : null,
)
const initialTab = computed(() => parseDetailTab(route.query.tab))

function goBack() {
  if (from.value === 'favorites' && window.history.length > 1) {
    void router.back()
    return
  }
  void router.push(
    detailBackRoute(from.value, {
      date: fromDate.value,
    }),
  )
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
        <BasicInfo v-if="data" :fixture="data" />
        <div v-else class="basic-info-skel">
          <n-breadcrumb>
            <n-breadcrumb-item @click="goBack">{{ rootLabel }}</n-breadcrumb-item>
            <n-breadcrumb-item>
              <n-skeleton text :width="72" :sharp="false" />
            </n-breadcrumb-item>
            <n-breadcrumb-item>
              <n-skeleton text :width="160" :sharp="false" />
            </n-breadcrumb-item>
          </n-breadcrumb>
          <n-skeleton text :width="240" style="margin-top: 12px" :sharp="false" />
          <n-skeleton text :width="180" style="margin-top: 8px" :sharp="false" />
        </div>

        <TabsContainer
          class="tabs-fill"
          :fixture="data"
          :pkg="data?.analysis.package ?? null"
          :loading="contentLoading"
          :error="error"
          :initial-tab="initialTab"
          @retry="reload"
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

.detail-body :deep(.basic-info),
.basic-info-skel {
  flex-shrink: 0;
}

.basic-info-skel {
  display: flex;
  flex-direction: column;
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
