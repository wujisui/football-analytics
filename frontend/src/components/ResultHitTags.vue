<script setup lang="ts">
import type { ResultFixture } from '@/api/fixtures'
import { hitLabel, hitTagType } from '@/utils/resultsDisplay'

defineProps<{
  fixture: ResultFixture
}>()
</script>

<template>
  <n-space v-if="fixture.has_prediction" :size="6" wrap>
    <n-tag size="small" :type="hitTagType(fixture.result_hit)" :bordered="false">
      胜平负 {{ hitLabel(fixture.result_hit) }}
    </n-tag>
    <n-tag size="small" :type="hitTagType(fixture.score_hit)" :bordered="false">
      比分 {{ hitLabel(fixture.score_hit) }}
    </n-tag>
    <n-tag size="small" :type="hitTagType(fixture.ou_hit)" :bordered="false">
      大小 {{ hitLabel(fixture.ou_hit) }}
    </n-tag>
    <n-tag size="small" :type="hitTagType(fixture.btts_hit)" :bordered="false">
      双方进球 {{ hitLabel(fixture.btts_hit) }}
    </n-tag>
  </n-space>
</template>
