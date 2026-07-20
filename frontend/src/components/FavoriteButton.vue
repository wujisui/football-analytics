<script setup lang="ts">
import { Star, StarOutline } from '@vicons/ionicons5'
import { computed } from 'vue'

import type { FixtureResponse } from '@/api/types'
import type { ResultFixture } from '@/api/fixtures'
import { useFavoriteFixtures } from '@/composables/useFavoriteFixtures'

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

function onClick(event: MouseEvent) {
  if (props.stopPropagation) event.stopPropagation()
  if (active.value) {
    remove(props.fixtureId)
    return
  }
  if (props.fixture) {
    toggleFixture(props.fixture)
    return
  }
  if (props.resultFixture) {
    toggleResultFixture(props.resultFixture)
  }
}
</script>

<template>
  <n-tooltip placement="top">
    <template #trigger>
      <n-button
        quaternary
        circle
        :size="size"
        :type="active ? 'warning' : 'default'"
        :aria-label="active ? '取消收藏' : '收藏'"
        @click="onClick"
      >
        <template #icon>
          <n-icon :component="active ? Star : StarOutline" />
        </template>
      </n-button>
    </template>
    {{ active ? '取消收藏' : '收藏' }}
  </n-tooltip>
</template>
