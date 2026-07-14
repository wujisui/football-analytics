import { ref } from 'vue'

import { fetchTodayFixtures } from '@/api/fixtures'
import type { FixtureResponse } from '@/api/types'

const LOOKAHEAD_DAYS = 7
/** Include yesterday so kickoff-delayed / in-play fixtures are not dropped. */
const LOOKBACK_DAYS = 1
/** Reuse list data across Home remounts (detail → back) within this TTL. */
const CACHE_TTL_MS = 5 * 60 * 1000

const allFixtures = ref<FixtureResponse[]>([])
const windowLabel = ref('')
const loadedAt = ref(0)
const loading = ref(false)
const error = ref('')
let inflight: Promise<void> | null = null

function cacheFresh(): boolean {
  return loadedAt.value > 0 && Date.now() - loadedAt.value < CACHE_TTL_MS
}

function isoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function homeWindowStartDate(): string {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() - LOOKBACK_DAYS)
  return isoDate(d)
}

function todayDate(): string {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return isoDate(d)
}

function homeWindowDays(): number {
  return LOOKAHEAD_DAYS + LOOKBACK_DAYS
}

/**
 * Load home window fixtures from local API only.
 * Client filters by tracked league ids — do not narrow with league_ids here
 * (extras from the reference catalog must remain visible after sync).
 */
async function loadHomeFixtures(options?: { force?: boolean }): Promise<void> {
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
      const fixturesData = await fetchTodayFixtures({ date, days })
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
    homeWindowDays,
    homeWindowStartDate,
    todayDate,
    allFixtures,
    windowLabel,
    loading,
    error,
    loadHomeFixtures,
  }
}
