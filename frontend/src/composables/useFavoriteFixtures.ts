import { computed, ref } from 'vue'

import type { FixtureResponse } from '@/api/types'
import type { ResultFixture } from '@/api/fixtures'
import {
  addFavorite,
  deleteFavorite,
  fetchFavorites,
  type FavoriteFixtureRecord,
} from '@/api/favorites'
import { oddsSnippetFromFixture } from '@/utils/oddsDisplay'
import { snapshotFromAnalysis, type PredictionSnapshot } from '@/utils/opinionAdjust'
import { toScheduleDayKey } from '@/utils/format'

export type { FavoriteFixtureRecord }

const favorites = ref<FavoriteFixtureRecord[]>([])
let loadPromise: Promise<void> | null = null
let loading = false

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

function optimisticFromFixture(fixture: FixtureResponse): FavoriteFixtureRecord {
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
    source: 'manual',
    auto_market: null,
    auto_lean: null,
    quality_rating: null,
    odds_snippet: oddsSnippetFromFixture(fixture),
    home_rank: fixture.home_rank ?? null,
    away_rank: fixture.away_rank ?? null,
    ...predictionFieldsFromSnapshot(snapshot),
  }
}

function optimisticFromResult(fixture: ResultFixture): FavoriteFixtureRecord {
  const hasPrediction = !!(
    fixture.has_prediction ||
    fixture.recommendation ||
    fixture.score_hint ||
    fixture.goal_lean ||
    fixture.both_score_lean
  )
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
    source: 'manual',
    auto_market: null,
    auto_lean: null,
    quality_rating: null,
    has_prediction: hasPrediction,
    recommendation: fixture.recommendation ?? undefined,
    handicap_lean: fixture.handicap_lean ?? undefined,
    score_hint: fixture.score_hint ?? undefined,
    goal_lean: fixture.goal_lean ?? undefined,
    both_score_lean: fixture.both_score_lean ?? undefined,
    handicap_result: fixture.handicap_result,
    handicap_hit: fixture.handicap_hit,
    score_hit: fixture.score_hit,
    ou_hit: fixture.ou_hit,
    btts_hit: fixture.btts_hit,
    result_hit: fixture.result_hit,
    auto_pick_hit: fixture.auto_pick_hit,
    home_rank: fixture.home_rank ?? null,
    away_rank: fixture.away_rank ?? null,
  }
}

async function loadFavorites(): Promise<void> {
  const data = await fetchFavorites()
  favorites.value = data.favorites
}

async function ensureLoaded(): Promise<void> {
  if (loadPromise) return loadPromise
  loading = true
  loadPromise = (async () => {
    try {
      await loadFavorites()
    } catch {
      /* keep empty until next reload */
    } finally {
      loading = false
    }
  })()
  return loadPromise
}

/** Force a re-read; a request already in flight is awaited instead of duplicated. */
async function refreshFavorites(): Promise<void> {
  if (loading && loadPromise) {
    await loadPromise
    return
  }
  loadPromise = null
  await ensureLoaded()
}

void ensureLoaded()

/** Drop the previous account's favorites before guest reload / login refresh. */
export function clearPrivateFavorites() {
  favorites.value = []
  loadPromise = null
  loading = false
}

const favoriteIds = computed(() => new Set(favorites.value.map((f) => f.fixture_id)))
const favoriteList = computed<FavoriteFixtureRecord[]>(() => favorites.value)

function isFavorite(fixtureId: number): boolean {
  return favoriteIds.value.has(fixtureId)
}

/** Schedule calendar days (YYYY-MM-DD) that have at least one favorite fixture. */
export function favoriteFixtureDays(
  favoritesList: readonly FavoriteFixtureRecord[],
): Set<string> {
  return new Set(favoritesList.map((item) => toScheduleDayKey(item.fixture_date)))
}

/**
 * Prefer ``preferred`` when it has favorites; otherwise the next upcoming day,
 * else the latest past day. Used so 关注 does not land on an empty "today"
 * while auto picks sit on later match days.
 */
export function nearestFavoriteDay(
  days: Iterable<string>,
  preferred: string,
): string | null {
  const sorted = [...new Set(days)].filter((day) => /^\d{4}-\d{2}-\d{2}$/.test(day)).sort()
  if (!sorted.length) return null
  if (sorted.includes(preferred)) return preferred
  return sorted.find((day) => day >= preferred) ?? sorted[sorted.length - 1]
}

export function favoriteHasPredictSnapshot(item: FavoriteFixtureRecord): boolean {
  return !!(
    item.has_prediction ||
    item.recommendation ||
    item.score_hint ||
    item.goal_lean ||
    item.both_score_lean
  )
}

/** Map favorite row → prediction card snapshot. */
export function snapshotFromFavorite(item: FavoriteFixtureRecord): PredictionSnapshot {
  const ready = !!item.probabilities_available
  return {
    home_win_prob: ready ? Number(item.home_win_prob ?? 0) : 0,
    draw_prob: ready ? Number(item.draw_prob ?? 0) : 0,
    away_win_prob: ready ? Number(item.away_win_prob ?? 0) : 0,
    recommendation: item.recommendation || '待分析',
    goal_lean: item.goal_lean || '',
    both_score_lean: item.both_score_lean || '',
    score_hint: item.score_hint || '',
    handicap_lean: item.handicap_lean || '',
    probabilitiesAvailable: ready,
  }
}

function upsertLocal(record: FavoriteFixtureRecord) {
  const next = favorites.value.filter((f) => f.fixture_id !== record.fixture_id)
  next.unshift(record)
  favorites.value = next
}

async function remove(fixtureId: number): Promise<void> {
  await ensureLoaded()
  const prev = favorites.value
  favorites.value = prev.filter((f) => f.fixture_id !== fixtureId)
  try {
    await deleteFavorite(fixtureId)
  } catch {
    favorites.value = prev
  }
}

async function toggleFixture(fixture: FixtureResponse): Promise<boolean> {
  await ensureLoaded()
  if (isFavorite(fixture.fixture_id)) {
    await remove(fixture.fixture_id)
    return false
  }
  const optimistic = optimisticFromFixture(fixture)
  upsertLocal(optimistic)
  try {
    const saved = await addFavorite(fixture.fixture_id)
    upsertLocal({
      ...saved,
      odds_snippet: saved.odds_snippet ?? optimistic.odds_snippet ?? null,
    })
    return true
  } catch {
    favorites.value = favorites.value.filter((f) => f.fixture_id !== fixture.fixture_id)
    return false
  }
}

async function toggleResultFixture(fixture: ResultFixture): Promise<boolean> {
  await ensureLoaded()
  if (isFavorite(fixture.fixture_id)) {
    await remove(fixture.fixture_id)
    return false
  }
  const optimistic = optimisticFromResult(fixture)
  upsertLocal(optimistic)
  try {
    const saved = await addFavorite(fixture.fixture_id)
    upsertLocal(saved)
    return true
  } catch {
    favorites.value = favorites.value.filter((f) => f.fixture_id !== fixture.fixture_id)
    return false
  }
}

/** Instant detail crumb while /analysis is still in flight. */
export function findFavoriteListFixture(
  fixtureId: number,
): FavoriteFixtureRecord | null {
  return favorites.value.find((f) => f.fixture_id === fixtureId) ?? null
}

/** Auto-pick market for highlight, or null when not an algorithm favorite. */
export function autoFavoriteMarket(
  fixtureId: number | null | undefined,
): string | null {
  if (fixtureId == null) return null
  const item = findFavoriteListFixture(fixtureId)
  if (!item || item.source !== 'auto') return null
  const market = (item.auto_market || '').trim()
  return market || null
}

/** 0.5–5 星推荐质量；非算法推荐或历史不足时为 null。 */
export function favoriteQualityRating(
  fixtureId: number | null | undefined,
): number | null {
  if (fixtureId == null) return null
  const item = findFavoriteListFixture(fixtureId)
  if (!item || item.source !== 'auto') return null
  const rating = Number(item.quality_rating ?? 0)
  return rating > 0 ? rating : null
}

export function useFavoriteFixtures() {
  return {
    favorites: favoriteList,
    favoriteIds,
    isFavorite,
    toggleFixture,
    toggleResultFixture,
    remove,
    ensureLoaded,
    refresh: refreshFavorites,
    clearPrivate: clearPrivateFavorites,
  }
}
