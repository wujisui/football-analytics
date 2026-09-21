/** Normalize frozen absolute recommendation-strength rating (1–5). */
export function normalizeQualityRating(value: unknown): number | null {
  const rating = Number(value ?? 0)
  return Number.isFinite(rating) && rating >= 1 && rating <= 5 ? rating : null
}
