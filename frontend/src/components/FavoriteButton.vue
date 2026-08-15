<script setup lang="ts">
import { Star, StarOutline } from '@vicons/ionicons5'
import { computed } from 'vue'

import type { FixtureResponse } from '@/api/types'
import type { ResultFixture } from '@/api/fixtures'
import { useAuthSession } from '@/composables/useAuthSession'
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
const { requireLogin } = useAuthSession()

const active = computed(() => isFavorite(props.fixtureId))

function onClick(event: MouseEvent) {
  if (props.stopPropagation) event.stopPropagation()
  if (!requireLogin()) return
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
    :type="active ? 'warning' : 'default'"
    :aria-label="active ? '取消关注' : '关注'"
    @click="onClick"
  >
    <template #icon>
      <n-icon :component="active ? Star : StarOutline" />
    </template>
  </n-button>
</template>
