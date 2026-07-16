import { ref } from 'vue'

import { fetchTodayFixtures } from '@/api/fixtures'
import type { FixtureResponse } from '@/api/types'
import { oddsPackageToSnippet } from '@/utils/oddsDisplay'

/** Reuse list data across page remounts (detail → back) within this TTL. */
const CACHE_TTL_MS = 5 * 60 * 1000
const DEFAULT_DAYS = 1

const allFixtures = ref<FixtureResponse[]>([])
const loadedAt = ref(0)
const loading = ref(false)
const error = ref('')
let loadedKey = ''
let inflight: Promise<void> | null = null

function isoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function todayDate(): string {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return isoDate(d)
}

function cacheKey(date: string, days: number): string {
  return `${date}|${days}`
}

function cacheFresh(date: string, days: number): boolean {
  return (
    loadedKey === cacheKey(date, days) &&
    loadedAt.value > 0 &&
    Date.now() - loadedAt.value < CACHE_TTL_MS
  )
}

function formatWindowLabel(startDate: string, days: number): string {
  const today = todayDate()
  if (days === 1 && startDate === today) return `${startDate}`
  return days > 1 ? `${startDate} 起 ${days} 天` : startDate
}

const windowLabel = ref(formatWindowLabel(todayDate(), DEFAULT_DAYS))

/**
 * Load fixtures for a single calendar day from local API only.
 * Client filters by tracked league ids — do not narrow with league_ids here
 * (extras from the reference catalog must remain visible after sync).
 */
async function loadHomeFixtures(options?: {
  force?: boolean
  date?: string
  days?: number
}): Promise<void> {
  const date = options?.date ?? todayDate()
  const days = options?.days ?? DEFAULT_DAYS

  if (!options?.force && cacheFresh(date, days)) {
    loading.value = false
    return
  }
  if (inflight) return inflight

  loading.value = true
  error.value = ''
  inflight = (async () => {
    try {
      const fixturesData = await fetchTodayFixtures({ date, days })
      allFixtures.value = fixturesData.fixtures
      windowLabel.value = formatWindowLabel(fixturesData.date, fixturesData.days)
      loadedAt.value = Date.now()
      loadedKey = cacheKey(date, days)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '获取失败'
      throw err
    } finally {
      loading.value = false
      inflight = null
    }
  })()

  return inflight
}

/** Merge detail fetch into home list cache (odds_snippet, ranks). */
export function patchFixtureFromDetail(fixture: FixtureResponse): void {
  const idx = allFixtures.value.findIndex((f) => f.fixture_id === fixture.fixture_id)
  if (idx < 0) return

  const prev = allFixtures.value[idx]
  const snippet =
    fixture.odds_snippet ??
    oddsPackageToSnippet(fixture.analysis?.package?.odds ?? null)

  const next: FixtureResponse = {
    ...prev,
    home_rank: fixture.home_rank ?? prev.home_rank,
    away_rank: fixture.away_rank ?? prev.away_rank,
    odds_snippet: snippet ?? prev.odds_snippet,
  }
  allFixtures.value = allFixtures.value.map((row, i) => (i === idx ? next : row))
}

export function useHomeFixtures() {
  return {
    todayDate,
    allFixtures,
    windowLabel,
    loading,
    error,
    loadHomeFixtures,
    patchFixtureFromDetail,
  }
}
