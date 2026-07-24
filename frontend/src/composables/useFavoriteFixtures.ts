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
    odds_snippet: oddsSnippetFromFixture(fixture),
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
    single_result_hit: fixture.single_result_hit,
  }
}

async function loadFavorites(): Promise<void> {
  const data = await fetchFavorites()
  favorites.value = data.favorites
}

async function ensureLoaded(): Promise<void> {
  if (loadPromise) return loadPromise
  loadPromise = (async () => {
    try {
      await loadFavorites()
    } catch {
      /* keep empty until next reload */
    }
  })()
  return loadPromise
}

void ensureLoaded()

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

/** Reload hydrated favorites from the backend. */
async function reloadFavorites(): Promise<void> {
  try {
    await loadFavorites()
  } catch {
    /* keep current cache */
  }
}

export function useFavoriteFixtures() {
  return {
    favorites: favoriteList,
    favoriteIds,
    isFavorite,
    toggleFixture,
    toggleResultFixture,
    remove,
    reloadFavorites,
  }
}
