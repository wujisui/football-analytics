<script setup lang="ts">
import { hitTagType, type HitTagFixture } from '@/utils/resultsDisplay'
import type { ResultsHitKey } from '@/utils/resultsPageState'
import { handicapLeanLabel } from '@/utils/handicapDisplay'

const props = withDefaults(
  defineProps<{
    fixture: HitTagFixture
    /** Enable click-to-filter on Results list. */
    filterable?: boolean
    activeHitKey?: ResultsHitKey | null
  }>(),
  {
    filterable: false,
    activeHitKey: null,
  },
)

const emit = defineEmits<{
  filterHit: [key: ResultsHitKey]
}>()

function onTagClick(key: ResultsHitKey, hit: boolean | null | undefined) {
  if (!props.filterable || hit == null) return
  emit('filterHit', key)
}
</script>

<template>
  <n-flex v-if="fixture.has_prediction" :size="6" class="hit-tags">
    <n-tag
      class="hit-tag"
      :class="{
        clickable: filterable && fixture.result_hit != null,
        active: activeHitKey === 'result',
      }"
      size="small"
      :type="hitTagType(fixture.result_hit)"
      :bordered="false"
      @click.stop="onTagClick('result', fixture.result_hit)"
    >
      胜平负
    </n-tag>
    <n-tag
      class="hit-tag"
      :class="{
        clickable: filterable && fixture.score_hit != null,
        active: activeHitKey === 'score',
      }"
      size="small"
      :type="hitTagType(fixture.score_hit)"
      :bordered="false"
      @click.stop="onTagClick('score', fixture.score_hit)"
    >
      比分
    </n-tag>
    <n-tag
      class="hit-tag"
      :class="{
        clickable: filterable && fixture.ou_hit != null,
        active: activeHitKey === 'ou',
      }"
      size="small"
      :type="hitTagType(fixture.ou_hit)"
      :bordered="false"
      @click.stop="onTagClick('ou', fixture.ou_hit)"
    >
      大小
    </n-tag>
    <n-tag
      class="hit-tag"
      :class="{
        clickable: filterable && fixture.btts_hit != null,
        active: activeHitKey === 'btts',
      }"
      size="small"
      :type="hitTagType(fixture.btts_hit)"
      :bordered="false"
      @click.stop="onTagClick('btts', fixture.btts_hit)"
    >
      双进
    </n-tag>
    <n-tag
      v-if="fixture.handicap_lean && fixture.handicap_hit != null"
      class="hit-tag"
      :class="{
        clickable: filterable,
        active: activeHitKey === 'handicap',
      }"
      size="small"
      :type="hitTagType(fixture.handicap_hit)"
      :bordered="false"
      @click.stop="onTagClick('handicap', fixture.handicap_hit)"
    >
      {{ handicapLeanLabel(fixture.handicap_lean) }}
    </n-tag>
  </n-flex>
</template>

<style scoped>
.hit-tag {
  padding: 4px 10px !important;
  height: auto !important;
  line-height: 1.35 !important;
  user-select: none;
}

.hit-tag.clickable {
  cursor: pointer;
}

.hit-tag.active {
  outline: 1px solid var(--fa-highlight-text);
  outline-offset: 1px;
}
</style>
