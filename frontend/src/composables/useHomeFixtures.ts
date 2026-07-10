import { ref } from 'vue'

import { fetchTodayFixtures } from '@/api/fixtures'
import { fetchLeagues } from '@/api/leagues'
import type { FixtureResponse, LeagueSummaryResponse } from '@/api/types'

const LOOKAHEAD_DAYS = 7
/** Reuse list data across Home remounts (detail → back) within this TTL. */
const CACHE_TTL_MS = 5 * 60 * 1000

const leagues = ref<LeagueSummaryResponse[]>([])
const allFixtures = ref<FixtureResponse[]>([])
const windowLabel = ref('')
const loadedAt = ref(0)
const loading = ref(false)
const error = ref('')
let inflight: Promise<void> | null = null

function cacheFresh(): boolean {
  return loadedAt.value > 0 && Date.now() - loadedAt.value < CACHE_TTL_MS
}

async function loadHomeFixtures(options?: { force?: boolean }): Promise<void> {
  // Detail → Home remounts the page; reuse in-memory list (local DB only, but still avoid churn).
  if (!options?.force && cacheFresh()) {
    loading.value = false
    return
  }
  if (inflight) return inflight

  loading.value = true
  error.value = ''
  inflight = (async () => {
    try {
      const [leaguesData, fixturesData] = await Promise.all([
        fetchLeagues({ days: LOOKAHEAD_DAYS }),
        fetchTodayFixtures({ days: LOOKAHEAD_DAYS }),
      ])
      leagues.value = leaguesData.leagues
      allFixtures.value = fixturesData.fixtures
      windowLabel.value =
        fixturesData.days > 1
          ? `${fixturesData.date} 起 ${fixturesData.days} 天`
          : fixturesData.date
      loadedAt.value = Date.now()
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载失败'
      throw err
    } finally {
      loading.value = false
      inflight = null
    }
  })()

  return inflight
}

export function useHomeFixtures() {
  return {
    LOOKAHEAD_DAYS,
    leagues,
    allFixtures,
    windowLabel,
    loading,
    error,
    loadedAt,
    loadHomeFixtures,
    cacheFresh,
  }
}
