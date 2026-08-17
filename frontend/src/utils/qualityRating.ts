/** Normalize frozen auto-pick star rating for display (0.5–5). */
export function normalizeQualityRating(value: unknown): number | null {
  const rating = Number(value ?? 0)
  return Number.isFinite(rating) && rating > 0 ? rating : null
}
