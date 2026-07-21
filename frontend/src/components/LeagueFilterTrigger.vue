<script setup lang="ts">
import { FilterOutline } from '@vicons/ionicons5'
import { ref, watch } from 'vue'

import LeagueFilterPanel from '@/components/LeagueFilterPanel.vue'
import type { LeagueFilterOption } from '@/api/leagues'
import { resolveTrackedSelection } from '@/utils/leagueFilterSelection'

const props = withDefaults(
  defineProps<{
    options: LeagueFilterOption[]
    trackedIds: number[]
    iconOnly?: boolean
    filterActive?: boolean
    confirming?: boolean
    finishedMode?: boolean
    drawerMode?: boolean
  }>(),
  {
    iconOnly: false,
    filterActive: false,
    confirming: false,
    finishedMode: false,
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
          class="league-filter-btn"
          :class="{ 'is-icon-only': iconOnly }"
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
      :style="{ width: 'min(420px, 92vw)' }"
      :segmented="{ content: true, footer: false }"
    >
      <LeagueFilterPanel
        v-model:draft="draft"
        :options="options"
        :finished-mode="finishedMode"
        stacked
        :confirming="confirming"
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
        class="league-filter-btn"
        :class="{ 'is-icon-only': iconOnly }"
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
      :finished-mode="finishedMode"
      compact-actions
      :confirming="confirming"
      @confirm="confirm"
    />
  </n-popover>
</template>

<style scoped>
.league-filter-btn:not(.is-icon-only) {
  padding-inline: 10px;
}

.league-filter-btn.is-icon-only {
  width: var(--n-height-small);
  height: var(--n-height-small);
  padding: 0;
  justify-content: center;
}
</style>
