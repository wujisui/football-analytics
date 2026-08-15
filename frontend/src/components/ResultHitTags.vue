<script setup lang="ts">
import { computed } from 'vue'

import type { AutoFavoriteMarket } from '@/api/favorites'
import { hitTagType, type HitTagFixture } from '@/utils/resultsDisplay'
import type { ResultsHitKey } from '@/utils/resultsPageState'
import { handicapLeanLabel } from '@/utils/handicapDisplay'

const props = withDefaults(
  defineProps<{
    fixture: HitTagFixture
    /** Enable click-to-filter on Results list. */
    filterable?: boolean
    activeHitKey?: ResultsHitKey | null
    /** Override the daily-pick market (favorites rows carry their own field). */
    highlightMarket?: AutoFavoriteMarket | string | null
  }>(),
  {
    filterable: false,
    activeHitKey: null,
    highlightMarket: null,
  },
)

const emit = defineEmits<{
  filterHit: [key: ResultsHitKey]
}>()

const showTags = computed(() => !!props.fixture.has_prediction)

const pickMarket = computed(() =>
  (props.highlightMarket ?? props.fixture.auto_pick_market ?? '').trim(),
)

/** 对齐【比赛】：不额外加标签，只在被推荐的玩法前面标 [荐]。 */
function isPick(market: AutoFavoriteMarket): boolean {
  return pickMarket.value === market
}

function onTagClick(key: ResultsHitKey, hit: boolean | null | undefined) {
  if (!props.filterable || hit == null) return
  emit('filterHit', key)
}
</script>

<template>
  <n-flex v-if="showTags" :size="6" class="hit-tags">
    <n-tag
      v-if="fixture.has_prediction"
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
      <span v-if="isPick('1x2')" class="hit-pick-mark">[荐]</span>
      胜平负
    </n-tag>
    <n-tag
      v-if="fixture.has_prediction"
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
      v-if="fixture.has_prediction"
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
      <span v-if="isPick('ou')" class="hit-pick-mark">[荐]</span>
      大小
    </n-tag>
    <n-tag
      v-if="fixture.has_prediction"
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
      <span v-if="isPick('btts')" class="hit-pick-mark">[荐]</span>
      双进
    </n-tag>
    <n-tag
      v-if="fixture.handicap_lean"
      class="hit-tag"
      :class="{
        clickable: filterable && fixture.handicap_hit != null,
        active: activeHitKey === 'handicap',
      }"
      size="small"
      :type="hitTagType(fixture.handicap_hit)"
      :bordered="false"
      @click.stop="onTagClick('handicap', fixture.handicap_hit)"
    >
      <span v-if="isPick('ah')" class="hit-pick-mark">[荐]</span>
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

.hit-pick-mark {
  margin-right: 3px;
  font-size: 11px;
  opacity: 0.95;
}

.hit-tag.active {
  outline: 1px solid var(--fa-highlight-text);
  outline-offset: 1px;
}
</style>
