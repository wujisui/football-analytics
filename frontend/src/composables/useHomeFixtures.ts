import { ref } from 'vue'

import { fetchTodayFixtures } from '@/api/fixtures'
import type { FixtureResponse } from '@/api/types'
import { mergeDetailIntoListFixture } from '@/utils/oddsDisplay'
import { prematchFetchParams, todayDate } from '@/utils/homeDateStrip'

export { todayDate }

/** Reuse list data across page remounts (detail → back) within this TTL. */
const CACHE_TTL_MS = 5 * 60 * 1000
const DEFAULT_DAYS = 1

const allFixtures = ref<FixtureResponse[]>([])
const loadedAt = ref(0)
const loading = ref(false)
const error = ref('')
let loadedKey = ''
let inflight: Promise<void> | null = null
let inflightKey = ''
let loadSeq = 0

/** Detail wrote odds/analysis to DB — refresh list when returning to Home. */
let detailListDirty = false
const pendingDetailPatches = new Map<number, FixtureResponse>()

function leagueKey(ids?: number[]): string {
  if (!ids?.length) return '-'
  return [...new Set(ids.map(Number).filter((n) => Number.isFinite(n)))]
    .sort((a, b) => a - b)
    .join(',')
}

function cacheKey(date: string, days: number, leagueIds?: number[]): string {
  return `${date}|${days}|${leagueKey(leagueIds)}`
}

function cacheFresh(date: string, days: number, leagueIds?: number[]): boolean {
  return (
    loadedKey === cacheKey(date, days, leagueIds) &&
    loadedAt.value > 0 &&
    Date.now() - loadedAt.value < CACHE_TTL_MS
  )
}

/** True when shared list cache matches 即时 UTC today + span + league set. */
export function isPrematchListCacheFresh(
  now = new Date(),
  leagueIds?: number[],
): boolean {
  const { date, days } = prematchFetchParams(now)
  return cacheFresh(date, days, leagueIds)
}

function applyPendingPatches(): void {
  if (!pendingDetailPatches.size || !allFixtures.value.length) return

  let rows = allFixtures.value
  let changed = false
  for (const [fixtureId, detail] of pendingDetailPatches) {
    const idx = rows.findIndex((f) => f.fixture_id === fixtureId)
    if (idx < 0) continue
    rows = rows.map((row, i) =>
      i === idx ? mergeDetailIntoListFixture(row, detail) : row,
    )
    pendingDetailPatches.delete(fixtureId)
    changed = true
  }
  if (changed) allFixtures.value = rows
}

/**
 * Merge detail analysis into the shared home/predictions list cache.
 * Queues the patch when the list row is not loaded yet.
 */
export function patchFixtureFromDetail(detail: FixtureResponse): void {
  detailListDirty = true
  pendingDetailPatches.set(detail.fixture_id, detail)

  const idx = allFixtures.value.findIndex((f) => f.fixture_id === detail.fixture_id)
  if (idx < 0) return

  allFixtures.value = allFixtures.value.map((row, i) =>
    i === idx ? mergeDetailIntoListFixture(row, detail) : row,
  )
  pendingDetailPatches.delete(detail.fixture_id)
}

/** Instant detail crumb while /analysis is still in flight. */
export function findPrematchListFixture(
  fixtureId: number,
): FixtureResponse | null {
  return allFixtures.value.find((f) => f.fixture_id === fixtureId) ?? null
}

/** Apply queued patches; reload local list only when a patch could not merge yet. */
export function syncHomeListAfterDetail(
  _date: string,
  leagueIds?: number[],
): void {
  applyPendingPatches()
  if (!detailListDirty) return
  detailListDirty = false
  if (pendingDetailPatches.size > 0) {
    const { date: fetchDate, days } = prematchFetchParams()
    void loadHomeFixtures({ force: true, date: fetchDate, days, leagueIds })
  }
}

/**
 * Load fixtures for the prematch window from local API only.
 * Narrow with ``leagueIds`` on the server — do not pull the full global day.
 * Do not call with 赛程 selectedDay; that must stay in scheduleFixtures.
 */
async function loadHomeFixtures(options?: {
  force?: boolean
  date?: string
  days?: number
  leagueIds?: number[]
}): Promise<void> {
  const date = options?.date ?? todayDate()
  const days = options?.days ?? DEFAULT_DAYS
  const leagueIds = options?.leagueIds
  const key = cacheKey(date, days, leagueIds)

  if (!leagueIds?.length) {
    allFixtures.value = []
    loadedAt.value = Date.now()
    loadedKey = key
    loading.value = false
    error.value = ''
    return
  }

  if (!options?.force && cacheFresh(date, days, leagueIds)) {
    loading.value = false
    applyPendingPatches()
    return
  }
  if (inflight && inflightKey === key) return inflight
  if (inflight) {
    try {
      await inflight
    } catch {
      /* previous request failed; continue with this key */
    }
    if (!options?.force && cacheFresh(date, days, leagueIds)) {
      applyPendingPatches()
      return
    }
  }

  const seq = ++loadSeq
  loading.value = true
  error.value = ''
  inflightKey = key
  inflight = (async () => {
    try {
      const fixturesData = await fetchTodayFixtures({ date, days, leagueIds })
      if (seq !== loadSeq) return
      allFixtures.value = fixturesData.fixtures
      loadedAt.value = Date.now()
      loadedKey = key
      applyPendingPatches()
    } catch (err) {
      if (seq !== loadSeq) return
      error.value = err instanceof Error ? err.message : '获取失败'
      throw err
    } finally {
      if (seq === loadSeq) {
        loading.value = false
        inflight = null
        inflightKey = ''
      }
    }
  })()

  return inflight
}

export function useHomeFixtures() {
  return {
    todayDate,
    allFixtures,
    loading,
    error,
    loadHomeFixtures,
    patchFixtureFromDetail,
    syncHomeListAfterDetail,
  }
}
