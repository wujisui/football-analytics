<script setup lang="ts">
import { FilterOutline } from '@vicons/ionicons5'
import { ref, watch } from 'vue'

import LeagueFilterPanel from '@/layouts/components/LeagueFilterPanel.vue'
import type { LeagueFilterOption } from '@/api/leagues'
import { resolveTrackedSelection } from '@/utils/leagueFilterSelection'

const props = withDefaults(
  defineProps<{
    options: LeagueFilterOption[]
    trackedIds: number[]
    iconOnly?: boolean
    filterActive?: boolean
    drawerMode?: boolean
  }>(),
  {
    iconOnly: false,
    filterActive: false,
    drawerMode: false,
  },
)

const emit = defineEmits<{
  confirm: [ids: number[]]
}>()

const show = ref(false)
const draft = ref<number[]>([])

watch(show, (open) => {
  if (!open) return
  draft.value = resolveTrackedSelection(props.options, props.trackedIds)
})

function confirm() {
  emit('confirm', [...draft.value])
  show.value = false
}
</script>

<template>
  <template v-if="drawerMode">
    <n-tooltip :disabled="!iconOnly" placement="right-end">
      <template #trigger>
        <n-button
          size="small"
          quaternary
          :circle="iconOnly"
          :type="filterActive ? 'primary' : 'default'"
          aria-label="筛选联赛"
          @click="show = true"
        >
          <template #icon>
            <n-icon :component="FilterOutline" :size="14" />
          </template>
          <span v-if="!iconOnly">筛选</span>
        </n-button>
      </template>
      联赛筛选
    </n-tooltip>

    <n-modal
      v-model:show="show"
      preset="card"
      title="联赛筛选"
      class="league-filter-modal"
      :style="{ width: 'min(560px, 94vw)', maxHeight: 'calc(100dvh - 48px)' }"
      content-style="display: flex; flex-direction: column; min-height: 0; padding: 16px;"
      :segmented="{ content: true, footer: false }"
    >
      <LeagueFilterPanel
        v-model:draft="draft"
        :options="options"
        stacked
        @confirm="confirm"
      />
    </n-modal>
  </template>

  <n-popover
    v-else
    v-model:show="show"
    trigger="hover"
    :delay="80"
    :duration="180"
    placement="right-start"
    :show-arrow="false"
    display-directive="show"
    to="body"
  >
    <template #trigger>
      <n-button
        size="small"
        quaternary
        :circle="iconOnly"
        :type="filterActive ? 'primary' : 'default'"
        aria-label="筛选联赛"
      >
        <template #icon>
          <n-icon :component="FilterOutline" :size="14" />
        </template>
        <span v-if="!iconOnly">筛选</span>
      </n-button>
    </template>
    <LeagueFilterPanel
      v-model:draft="draft"
      :options="options"
      compact-actions
      @confirm="confirm"
    />
  </n-popover>
</template>

<style scoped>
.league-filter-modal {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.league-filter-modal :deep(.n-card__content) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>
