<script setup lang="ts">
import { Star, StarOutline } from '@vicons/ionicons5'
import { computed } from 'vue'

import type { FixtureResponse } from '@/api/types'
import type { ResultFixture } from '@/api/fixtures'
import {
  favoriteQualityLow,
  useFavoriteFixtures,
} from '@/composables/useFavoriteFixtures'

const props = withDefaults(
  defineProps<{
    fixtureId: number
    fixture?: FixtureResponse
    resultFixture?: ResultFixture
    size?: 'tiny' | 'small' | 'medium'
    /** Stop click from bubbling to parent cards/links. */
    stopPropagation?: boolean
  }>(),
  { size: 'small', stopPropagation: true },
)

const { isFavorite, toggleFixture, toggleResultFixture, remove } = useFavoriteFixtures()

const active = computed(() => isFavorite(props.fixtureId))
const qualityLow = computed(
  () => active.value && favoriteQualityLow(props.fixtureId),
)

function onClick(event: MouseEvent) {
  if (props.stopPropagation) event.stopPropagation()
  if (active.value) {
    void remove(props.fixtureId)
    return
  }
  if (props.fixture) {
    void toggleFixture(props.fixture)
    return
  }
  if (props.resultFixture) {
    void toggleResultFixture(props.resultFixture)
  }
}
</script>

<template>
  <n-button
    quaternary
    circle
    :size="size"
    :type="active && !qualityLow ? 'warning' : 'default'"
    :class="{ 'favorite-btn--quality-low': qualityLow }"
    :aria-label="
      active
        ? qualityLow
          ? '取消关注（质量偏低）'
          : '取消关注'
        : '关注'
    "
    @click="onClick"
  >
    <template #icon>
      <n-icon :component="active ? Star : StarOutline" />
    </template>
  </n-button>
</template>

<style scoped>
/* Second-tier star: filled but muted via shell tokens (normal stays warning gold). */
.favorite-btn--quality-low :deep(.n-icon) {
  color: var(--fa-text-muted);
}
</style>
