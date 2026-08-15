import { parseApiDate } from '@/utils/format'

/** Daily picks first, then favorites, then kickoff time. */
export function sortFixturesFavoritesFirst<
  T extends { fixture_id: number; fixture_date: string },
>(
  list: readonly T[],
  favoriteIds: ReadonlySet<number>,
  dailyPickIds: ReadonlySet<number> = new Set(),
): T[] {
  return list.slice().sort((a, b) => {
    const aPick = dailyPickIds.has(a.fixture_id)
    const bPick = dailyPickIds.has(b.fixture_id)
    if (aPick !== bPick) return aPick ? -1 : 1
    const aFav = favoriteIds.has(a.fixture_id)
    const bFav = favoriteIds.has(b.fixture_id)
    if (aFav !== bFav) return aFav ? -1 : 1
    return (
      parseApiDate(a.fixture_date).getTime() -
      parseApiDate(b.fixture_date).getTime()
    )
  })
}
