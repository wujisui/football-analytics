<script setup lang="ts">
import type { FixtureResponse } from '@/api/types'
import FixtureCard from '@/components/FixtureCard.vue'

defineProps<{
  fixtures: FixtureResponse[]
  emptyDescription?: string
}>()
</script>

<template>
  <div class="fixture-list">
    <n-empty
      v-if="fixtures.length === 0"
      :description="emptyDescription || '近期暂无该联赛赛事'"
      class="empty"
    />
    <FixtureCard
      v-for="fixture in fixtures"
      :key="fixture.fixture_id"
      :fixture="fixture"
    />
  </div>
</template>

<style scoped>
.fixture-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.empty {
  padding: 48px 0;
  background: var(--fa-bg-elevated);
  border: 1px dashed var(--fa-border);
  border-radius: 8px;
}
</style>
