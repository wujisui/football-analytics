<script setup lang="ts">
import { computed, ref } from 'vue'

import OpinionInput from '@/components/detail/OpinionInput.vue'
import PredictionResult from '@/components/detail/PredictionResult.vue'
import { adjustFixturePrediction } from '@/api/fixtures'
import type { FixtureResponse, PredictionSnapshot } from '@/api/types'
import { snapshotFromAnalysis } from '@/utils/opinionAdjust'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{
  fixture: FixtureResponse
}>()

const selectedFactors = ref<string[]>([])
const submittedFactors = ref<string[]>([])
const submitting = ref(false)
const adjustError = ref('')
const adjusted = ref<PredictionSnapshot | null>(null)

const original = computed(() => snapshotFromAnalysis(props.fixture.analysis))

async function submitOpinion() {
  if (!selectedFactors.value.length) return
  submitting.value = true
  adjustError.value = ''
  try {
    adjusted.value = await adjustFixturePrediction(
      props.fixture.fixture_id,
      selectedFactors.value,
    )
    submittedFactors.value = [...selectedFactors.value]
  } catch (e) {
    adjustError.value = e instanceof Error ? e.message : '融合预测失败'
    adjusted.value = null
    submittedFactors.value = []
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="prediction-tab">
    <OpinionInput
      v-model="selectedFactors"
      :submitting="submitting"
      @submit="submitOpinion"
    />
    <n-alert v-if="adjustError" type="error" :title="adjustError" />
    <PredictionResult
      :original="original"
      :adjusted="adjusted"
      :confidence="fixture.analysis.confidence"
      :data-source="fixture.analysis.data_source"
      :analyzed-at="formatDateTime(fixture.analysis.analyzed_at)"
      :comparing="submitting"
      :has-opinion="submittedFactors.length > 0"
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
