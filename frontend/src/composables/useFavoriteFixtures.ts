import { computed, ref } from 'vue'

import type { FixtureResponse } from '@/api/types'
import type { ResultFixture } from '@/api/fixtures'
import { snapshotFromAnalysis } from '@/utils/opinionAdjust'

const STORAGE_KEY = 'fa-favorite-fixtures'

export interface FavoriteFixtureRecord {
  fixture_id: number
  home_team_name: string
  away_team_name: string
  league_id: number
  league_name: string
  league_country?: string | null
  fixture_date: string
  status?: string
  home_goals?: number | null
  away_goals?: number | null
  saved_at: string
  has_prediction?: boolean
  recommendation?: string
  handicap_lean?: string
  score_hint?: string
  goal_lean?: string
  both_score_lean?: string
  probabilities_available?: boolean
  home_win_prob?: number
  draw_prob?: number
  away_win_prob?: number
}

function predictionFieldsFromResult(fixture: ResultFixture) {
  const hasPrediction = !!(
    fixture.has_prediction ||
    fixture.recommendation ||
    fixture.score_hint ||
    fixture.goal_lean ||
    fixture.both_score_lean
  )
  return {
    has_prediction: hasPrediction,
    recommendation: fixture.recommendation ?? undefined,
    score_hint: fixture.score_hint ?? undefined,
    goal_lean: fixture.goal_lean ?? undefined,
    both_score_lean: fixture.both_score_lean ?? undefined,
  }
}

function predictionFieldsFromSnapshot(snapshot: ReturnType<typeof snapshotFromAnalysis>) {
  return {
    has_prediction: snapshot.probabilitiesAvailable || !!snapshot.recommendation,
    recommendation: snapshot.recommendation || undefined,
    handicap_lean: snapshot.handicap_lean || undefined,
    score_hint: snapshot.score_hint || undefined,
    goal_lean: snapshot.goal_lean || undefined,
    both_score_lean: snapshot.both_score_lean || undefined,
    probabilities_available: snapshot.probabilitiesAvailable,
    home_win_prob: snapshot.probabilitiesAvailable ? snapshot.home_win_prob : undefined,
    draw_prob: snapshot.probabilitiesAvailable ? snapshot.draw_prob : undefined,
    away_win_prob: snapshot.probabilitiesAvailable ? snapshot.away_win_prob : undefined,
  }
}

function parseOptionalString(value: unknown): string | undefined {
  if (value == null || value === '') return undefined
  return String(value)
}

function parseOptionalNumber(value: unknown): number | undefined {
  if (value == null || value === '') return undefined
  const n = Number(value)
  return Number.isFinite(n) ? n : undefined
}

const favorites = ref<FavoriteFixtureRecord[]>([])

function readStored(): FavoriteFixtureRecord[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .map((item) => ({
        fixture_id: Number(item.fixture_id),
        home_team_name: String(item.home_team_name ?? ''),
        away_team_name: String(item.away_team_name ?? ''),
        league_id: Number(item.league_id),
        league_name: String(item.league_name ?? ''),
        league_country:
          item.league_country == null ? null : String(item.league_country),
        fixture_date: String(item.fixture_date ?? ''),
        status: item.status != null ? String(item.status) : undefined,
        home_goals:
          item.home_goals == null ? null : Number(item.home_goals),
        away_goals:
          item.away_goals == null ? null : Number(item.away_goals),
        saved_at: String(item.saved_at ?? new Date().toISOString()),
        has_prediction: item.has_prediction === true,
        recommendation: parseOptionalString(item.recommendation),
        handicap_lean: parseOptionalString(item.handicap_lean),
        score_hint: parseOptionalString(item.score_hint),
        goal_lean: parseOptionalString(item.goal_lean),
        both_score_lean: parseOptionalString(item.both_score_lean),
        probabilities_available: item.probabilities_available === true,
        home_win_prob: parseOptionalNumber(item.home_win_prob),
        draw_prob: parseOptionalNumber(item.draw_prob),
        away_win_prob: parseOptionalNumber(item.away_win_prob),
      }))
      .filter((item) => Number.isFinite(item.fixture_id) && item.fixture_id > 0)
  } catch {
    return []
  }
}

function persist(list: FavoriteFixtureRecord[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
  } catch {
    /* ignore */
  }
}

function ensureLoaded() {
  if (favorites.value.length || readStored().length) {
    favorites.value = readStored()
  }
}

ensureLoaded()

const favoriteIds = computed(() => new Set(favorites.value.map((f) => f.fixture_id)))

function isFavorite(fixtureId: number): boolean {
  return favoriteIds.value.has(fixtureId)
}

function favoriteHasPredictSnapshot(item: FavoriteFixtureRecord): boolean {
  return !!(
    item.has_prediction ||
    item.recommendation ||
    item.score_hint ||
    item.goal_lean ||
    item.both_score_lean
  )
}

function syncFavoriteFromResult(result: ResultFixture): boolean {
  const idx = favorites.value.findIndex((f) => f.fixture_id === result.fixture_id)
  if (idx < 0) return false
  const prev = favorites.value[idx]
  const prediction = predictionFieldsFromResult(result)
  const next = [...favorites.value]
  next[idx] = {
    ...prev,
    status: result.status,
    home_goals: result.home_goals,
    away_goals: result.away_goals,
    ...prediction,
  }
  favorites.value = next
  persist(next)
  return favoriteHasPredictSnapshot(next[idx])
}

function syncFavoriteFromFixture(fixture: FixtureResponse): boolean {
  const idx = favorites.value.findIndex((f) => f.fixture_id === fixture.fixture_id)
  if (idx < 0) return false
  const prev = favorites.value[idx]
  const prediction = predictionFieldsFromSnapshot(snapshotFromAnalysis(fixture.analysis))
  const next = [...favorites.value]
  next[idx] = {
    ...prev,
    status: fixture.status,
    home_goals: fixture.home_goals,
    away_goals: fixture.away_goals,
    ...prediction,
  }
  favorites.value = next
  persist(next)
  return favoriteHasPredictSnapshot(next[idx])
}

function recordFromFixture(fixture: FixtureResponse): FavoriteFixtureRecord {
  const snapshot = snapshotFromAnalysis(fixture.analysis)
  return {
    fixture_id: fixture.fixture_id,
    home_team_name: fixture.home_team_name,
    away_team_name: fixture.away_team_name,
    league_id: fixture.league_id,
    league_name: fixture.league_name,
    league_country: fixture.league_country ?? null,
    fixture_date: fixture.fixture_date,
    status: fixture.status,
    home_goals: fixture.home_goals,
    away_goals: fixture.away_goals,
    saved_at: new Date().toISOString(),
    ...predictionFieldsFromSnapshot(snapshot),
  }
}

function recordFromResult(fixture: ResultFixture): FavoriteFixtureRecord {
  return {
    fixture_id: fixture.fixture_id,
    home_team_name: fixture.home_team_name,
    away_team_name: fixture.away_team_name,
    league_id: fixture.league_id,
    league_name: fixture.league_name,
    league_country: fixture.league_country ?? null,
    fixture_date: fixture.fixture_date,
    status: fixture.status,
    home_goals: fixture.home_goals,
    away_goals: fixture.away_goals,
    saved_at: new Date().toISOString(),
    ...predictionFieldsFromResult(fixture),
  }
}

function upsert(record: FavoriteFixtureRecord) {
  const next = favorites.value.filter((f) => f.fixture_id !== record.fixture_id)
  next.unshift({ ...record, saved_at: new Date().toISOString() })
  favorites.value = next
  persist(next)
}

function remove(fixtureId: number) {
  const next = favorites.value.filter((f) => f.fixture_id !== fixtureId)
  favorites.value = next
  persist(next)
}

function toggleFixture(fixture: FixtureResponse) {
  if (isFavorite(fixture.fixture_id)) {
    remove(fixture.fixture_id)
    return false
  }
  upsert(recordFromFixture(fixture))
  return true
}

function toggleResultFixture(fixture: ResultFixture) {
  if (isFavorite(fixture.fixture_id)) {
    remove(fixture.fixture_id)
    return false
  }
  upsert(recordFromResult(fixture))
  return true
}

function fixtureDay(iso: string): string {
  return iso.slice(0, 10)
}

/** Backfill missing prediction snapshots from local DB (same source as 赛果页). */
async function refreshFavoritePredictions(): Promise<void> {
  const { fetchResults, fetchFixtureAnalysis } = await import('@/api/fixtures')

  let missing = favorites.value.filter((f) => !favoriteHasPredictSnapshot(f))
  if (!missing.length) return

  const dates = [...new Set(missing.map((f) => fixtureDay(f.fixture_date)))]
  for (const date of dates) {
    try {
      const { fixtures: dayFixtures } = await fetchResults(date)
      for (const fx of dayFixtures) {
        if (isFavorite(fx.fixture_id)) syncFavoriteFromResult(fx)
      }
    } catch {
      /* ignore per-day failures */
    }
  }

  missing = favorites.value.filter((f) => !favoriteHasPredictSnapshot(f))
  for (const item of missing.slice(0, 12)) {
    try {
      const fx = await fetchFixtureAnalysis(item.fixture_id)
      syncFavoriteFromFixture(fx)
    } catch {
      /* ignore per-fixture failures */
    }
  }
}

export function useFavoriteFixtures() {
  return {
    favorites,
    favoriteIds,
    isFavorite,
    toggleFixture,
    toggleResultFixture,
    remove,
    syncFavoriteFromResult,
    favoriteHasPredictSnapshot,
    refreshFavoritePredictions,
  }
}
