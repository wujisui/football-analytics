<script setup lang="ts">
import { computed, ref } from 'vue'

import OpinionInput from '@/components/detail/OpinionInput.vue'
import PredictionResult from '@/components/detail/PredictionResult.vue'
import type { FixtureResponse } from '@/api/types'
import {
  adjustWithOpinion,
  toPredictionSnapshot,
  type PredictionSnapshot,
} from '@/utils/opinionAdjust'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{
  fixture: FixtureResponse
}>()

const opinion = ref('')
const submittedOpinion = ref('')
const submitting = ref(false)
const adjusted = ref<PredictionSnapshot | null>(null)

const original = computed(() =>
  toPredictionSnapshot(
    props.fixture.analysis.probabilities,
    props.fixture.analysis.recommendation,
  ),
)

function submitOpinion() {
  if (!opinion.value.trim()) return
  submitting.value = true
  window.setTimeout(() => {
    adjusted.value = adjustWithOpinion(
      props.fixture.analysis.probabilities,
      opinion.value,
    )
    submittedOpinion.value = opinion.value.trim()
    submitting.value = false
  }, 280)
}
</script>

<template>
  <div class="prediction-tab">
    <OpinionInput
      v-model="opinion"
      :submitting="submitting"
      @submit="submitOpinion"
    />
    <PredictionResult
      :original="original"
      :adjusted="adjusted"
      :confidence="fixture.analysis.confidence"
      :data-source="fixture.analysis.data_source"
      :analyzed-at="formatDateTime(fixture.analysis.analyzed_at)"
      :comparing="submitting"
      :has-opinion="!!submittedOpinion"
    />
  </div>
</template>

<style scoped>
.prediction-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
