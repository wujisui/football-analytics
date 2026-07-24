<script setup lang="ts">
import { hitTagType, type HitTagFixture } from '@/utils/resultsDisplay'

defineProps<{
  fixture: HitTagFixture
}>()
</script>

<template>
  <div v-if="fixture.has_prediction" class="hit-tags">
    <n-tag size="small" :type="hitTagType(fixture.result_hit)" :bordered="false">
      胜平负
    </n-tag>
    <n-tag size="small" :type="hitTagType(fixture.score_hit)" :bordered="false">
      比分
    </n-tag>
    <n-tag size="small" :type="hitTagType(fixture.ou_hit)" :bordered="false">
      大小
    </n-tag>
    <n-tag size="small" :type="hitTagType(fixture.btts_hit)" :bordered="false">
      双进
    </n-tag>
    <n-tag
      v-if="fixture.handicap_result && fixture.handicap_hit != null"
      size="small"
      :type="hitTagType(fixture.handicap_hit)"
      :bordered="false"
    >
      {{ fixture.handicap_result }}
    </n-tag>
  </div>
</template>

<style scoped>
.hit-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
  max-width: 100%;
}
</style>
