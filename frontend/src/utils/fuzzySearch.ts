/** Lightweight fuzzy match: contiguous substring or ordered subsequence. */

function normalize(text: string): string {
  return text.trim().toLowerCase()
}

/**
 * True when `query` is empty, `text` contains `query`, or every query char
 * appears in `text` in order (e.g. 「曼联」→「曼彻斯特联」).
 */
export function fuzzyIncludes(text: string, query: string): boolean {
  const t = normalize(text)
  const q = normalize(query)
  if (!q) return true
  if (!t) return false
  if (t.includes(q)) return true

  let from = 0
  for (const ch of q) {
    const idx = t.indexOf(ch, from)
    if (idx === -1) return false
    from = idx + 1
  }
  return true
}

/** True when any non-empty field fuzzy-matches the query. */
export function fuzzyMatchAny(
  query: string,
  fields: readonly (string | null | undefined)[],
): boolean {
  const q = query.trim()
  if (!q) return true
  return fields.some((field) => field && fuzzyIncludes(field, q))
}
