<script setup lang="ts">
import { TrashOutline } from '@vicons/ionicons5'

import { leagueTagColor } from '@/utils/format'
import type { GroupedFixtureSelections } from '@/views/Predictions/composables/useBetCalculator'

defineProps<{
  groups: GroupedFixtureSelections[]
  emptyDescription?: string
}>()

const emit = defineEmits<{
  remove: [fixtureId: number]
}>()
</script>

<template>
  <div class="selection-list">
    <n-empty
      v-if="!groups.length"
      :description="emptyDescription || '暂无已选场次'"
      size="small"
    />
    <n-card
      v-for="group in groups"
      v-else
      :key="group.fixtureId"
      size="small"
      :bordered="false"
      header-style="font-size: inherit; font-weight: 400;"
      class="selection-card"
    >
      <template #header>
        <n-flex :wrap="false" align="center" :size="8" style="min-width: 0;">
          <n-ellipsis style="flex: 0 1 auto; min-width: 0;">
            <n-text :style="{ color: leagueTagColor(group.leagueId) }">
              {{ group.leagueName }}
            </n-text>
          </n-ellipsis>
          <n-text depth="3" style="flex-shrink: 0; font-size: 12px;">
            {{ group.kickoff }}
          </n-text>
        </n-flex>
      </template>
      <template #header-extra>
        <n-button
          size="tiny"
          type="error"
          quaternary
          circle
          aria-label="移除场次"
          @click="emit('remove', group.fixtureId)"
        >
          <template #icon>
            <n-icon :component="TrashOutline" />
          </template>
        </n-button>
      </template>

      <n-flex vertical :size="8">
        <n-flex
          :wrap="false"
          justify="center"
          align="center"
          :size="6"
          class="matchup"
        >
          <n-ellipsis>{{ group.homeName }}</n-ellipsis>
          <n-text depth="3" class="versus">VS</n-text>
          <n-ellipsis>{{ group.awayName }}</n-ellipsis>
        </n-flex>
        <n-flex
          v-for="pick in group.picks"
          :key="`${pick.market}-${pick.outcome}`"
          :wrap="false"
          align="center"
          :size="8"
        >
          <n-tag size="small" :bordered="false">{{ pick.playLabel }}</n-tag>
          <n-tag size="small" :bordered="false" type="warning">
            {{ pick.pickLabel }}
          </n-tag>
        </n-flex>
      </n-flex>
    </n-card>
  </div>
</template>

<style scoped>
.selection-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
}

.selection-card {
  background: var(--fa-bg-soft);
}

.selection-card :deep(.n-card-header),
.selection-card :deep(.n-card__content) {
  padding: 8px;
}

.selection-card :deep(.n-card-header__main) {
  min-width: 0;
}

.matchup {
  width: 100%;
  min-width: 0;
}

.matchup :deep(.n-ellipsis) {
  flex: 0 1 auto;
  min-width: 0;
  font-weight: 600;
}

.versus {
  flex: 0 0 auto;
  white-space: nowrap;
}
</style>
