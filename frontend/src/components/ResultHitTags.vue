<script setup lang="ts">
import { computed } from 'vue'

import type { AutoFavoriteMarket } from '@/api/favorites'
import RecommendationQualityRate from '@/components/RecommendationQualityRate.vue'
import { useHandicapRuleset } from '@/composables/useHandicapRuleset'
import { adaptHandicapLean, handicapLeanLabel } from '@/utils/handicapDisplay'
import { hitTagMissed, hitTagType, type HitTagFixture } from '@/utils/resultsDisplay'
import type { ResultsHitKey } from '@/utils/resultsPageState'

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

const { ruleset } = useHandicapRuleset()

const handicapTagLabel = computed(() =>
  handicapLeanLabel(adaptHandicapLean(props.fixture.handicap_lean, ruleset.value)),
)

const showTags = computed(() => !!props.fixture.has_prediction)

const pickMarket = computed(() => (props.fixture.auto_pick_market ?? '').trim())

/** 对齐【比赛】：不额外加标签，只在被推荐的玩法前面标 [荐]。 */
function isPick(market: AutoFavoriteMarket): boolean {
  return pickMarket.value === market
}

function onTagClick(key: ResultsHitKey, hit: boolean | null | undefined) {
  if (!props.filterable || hit !== true) return
  emit('filterHit', key)
}
</script>

<template>
  <n-flex v-if="showTags" :size="6" class="hit-tags">
    <n-tag
      v-if="fixture.has_prediction"
      class="hit-tag"
      :class="{
        clickable: filterable && fixture.result_hit === true,
        'fa-tag-missed': hitTagMissed(fixture.result_hit),
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
        clickable: filterable && fixture.score_hit === true,
        'fa-tag-missed': hitTagMissed(fixture.score_hit),
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
        clickable: filterable && fixture.ou_hit === true,
        'fa-tag-missed': hitTagMissed(fixture.ou_hit),
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
        clickable: filterable && fixture.btts_hit === true,
        'fa-tag-missed': hitTagMissed(fixture.btts_hit),
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
        clickable: filterable && fixture.handicap_hit === true,
        'fa-tag-missed': hitTagMissed(fixture.handicap_hit),
        active: activeHitKey === 'handicap',
      }"
      size="small"
      :type="hitTagType(fixture.handicap_hit)"
      :bordered="false"
      @click.stop="onTagClick('handicap', fixture.handicap_hit)"
    >
      <span v-if="isPick('ah')" class="hit-pick-mark">[荐]</span>
      {{ handicapTagLabel }}
    </n-tag>
    <RecommendationQualityRate
      class="hit-rate"
      :value="fixture.quality_rating"
      @click.stop
    />
  </n-flex>
</template>

<style scoped>
.hit-tag {
  padding: 4px 10px !important;
  height: auto !important;
  line-height: 1.35 !important;
}

.hit-tag.clickable {
  cursor: pointer;
}

.hit-pick-mark {
  margin-right: 3px;
  font-size: 11px;
  opacity: 0.95;
}

/* 跟着标签一起换行，落在最后一枚标签后面 */
.hit-rate {
  align-self: center;
}

.hit-tag.active {
  outline: 1px solid var(--fa-highlight-text);
  outline-offset: 1px;
}
</style>
