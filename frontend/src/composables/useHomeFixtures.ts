import { ref } from 'vue'

import { fetchTodayFixtures } from '@/api/fixtures'
import { fetchLeagues } from '@/api/leagues'
import type { FixtureResponse, LeagueSummaryResponse } from '@/api/types'

const LOOKAHEAD_DAYS = 7
/** Include yesterday so kickoff-delayed / in-play fixtures are not dropped. */
const LOOKBACK_DAYS = 1
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

function homeWindowStartDate(): string {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() - LOOKBACK_DAYS)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function homeWindowDays(): number {
  return LOOKAHEAD_DAYS + LOOKBACK_DAYS
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
      const days = homeWindowDays()
      const date = homeWindowStartDate()
      const [leaguesData, fixturesData] = await Promise.all([
        fetchLeagues({ days }),
        fetchTodayFixtures({ date, days }),
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
    LOOKBACK_DAYS,
    homeWindowDays,
    homeWindowStartDate,
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
