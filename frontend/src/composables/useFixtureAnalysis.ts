import { ref, type Ref } from 'vue'

import { fetchFixtureAnalysis } from '@/api/fixtures'
import type { FixtureResponse } from '@/api/types'

/**
 * Lazy-load + cache for GET /fixtures/{id}/analysis.
 * Detail tabs share one request; per-tab endpoints in FRONTEND_UI_SPEC are not available yet.
 */
export function useFixtureAnalysis(fixtureId: Ref<number>) {
  const data = ref<FixtureResponse | null>(null)
  const loading = ref(false)
  const error = ref('')
  const loaded = ref(false)

  let inflight: Promise<FixtureResponse | null> | null = null

  function reset() {
    data.value = null
    loading.value = false
    error.value = ''
    loaded.value = false
    inflight = null
  }

  async function ensureLoaded(): Promise<FixtureResponse | null> {
    if (loaded.value && data.value) return data.value
    if (inflight) return inflight

    if (Number.isNaN(fixtureId.value)) {
      error.value = '无效的比赛 ID'
      loaded.value = true
      return null
    }

    loading.value = true
    error.value = ''

    inflight = (async () => {
      try {
        const result = await fetchFixtureAnalysis(fixtureId.value)
        data.value = result
        loaded.value = true
        return result
      } catch (err) {
        error.value = err instanceof Error ? err.message : '加载分析失败'
        loaded.value = false
        return null
      } finally {
        loading.value = false
        inflight = null
      }
    })()

    return inflight
  }

  async function reload(): Promise<FixtureResponse | null> {
    reset()
    return ensureLoaded()
  }

  return {
    data,
    loading,
    error,
    loaded,
    ensureLoaded,
    reload,
    reset,
  }
}
