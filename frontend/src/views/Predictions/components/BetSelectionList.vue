<script setup lang="ts">
import { TrashOutline } from '@vicons/ionicons5'

import FixtureMatchup from '@/components/FixtureMatchup.vue'
import {
  outcomeTitle,
  type CalcOutcome,
  type CalcSelection,
} from '@/utils/betCalculator'
import { leagueTagColor } from '@/utils/format'
import type { GroupedFixtureSelections } from '@/views/Predictions/composables/useBetCalculator'

defineProps<{
  groups: GroupedFixtureSelections[]
  emptyDescription?: string
}>()

const emit = defineEmits<{
  remove: [fixtureId: number]
}>()

const OUTCOME_ORDER: CalcOutcome[] = [
  'home',
  'draw',
  'away',
  'over',
  'under',
  'yes',
  'no',
]

/** Same market dual-picks share one play tag + one combined pick tag. */
function pickRows(picks: CalcSelection[]) {
  const buckets = new Map<string, CalcSelection[]>()
  for (const pick of picks) {
    const key = `${pick.market}\0${pick.line ?? ''}\0${pick.playLabel}`
    const list = buckets.get(key) ?? []
    list.push(pick)
    buckets.set(key, list)
  }
  return [...buckets.entries()].map(([key, list]) => {
    const sorted = [...list].sort(
      (a, b) =>
        OUTCOME_ORDER.indexOf(a.outcome) - OUTCOME_ORDER.indexOf(b.outcome),
    )
    return {
      key,
      playLabel: sorted[0].playLabel,
      pickLabel: sorted
        .map((p) => `${outcomeTitle(p.market, p.outcome)}(${p.odd})`)
        .join('，'),
    }
  })
}
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
          data-export-hide
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

      <n-flex vertical :size="4">
        <FixtureMatchup
          :home-name="group.homeName"
          :away-name="group.awayName"
        />
        <n-flex
          v-for="row in pickRows(group.picks)"
          :key="row.key"
          :wrap="false"
          align="center"
          :size="6"
        >
          <n-tag size="small" :bordered="false">{{ row.playLabel }}</n-tag>
          <n-tag size="small" :bordered="false" type="warning">
            {{ row.pickLabel }}
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
  gap: 6px;
  padding:1px 10px 12px;
}

.selection-card {
  background: var(--fa-bg-soft);
}

/* Compact rows: fit one more fixture per viewport in the details list. */
.selection-card :deep(.n-card-header) {
  padding: 5px 8px 0;
  line-height: 1.3;
}

.selection-card :deep(.n-card__content) {
  padding: 4px 8px 6px;
}

.selection-card :deep(.n-card-header__main) {
  min-width: 0;
  font-size: 12px;
}

.selection-card :deep(.n-card-header__extra) {
  margin-left: 6px;
}

.selection-card :deep(.n-tag) {
  --n-height: 20px;
}
</style>
