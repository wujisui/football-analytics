import { parseApiDate } from '@/utils/format'

/** Favorites first, then kickoff time (same rule for 即时 / 赛果 lists). */
export function sortFixturesFavoritesFirst<
  T extends { fixture_id: number; fixture_date: string },
>(list: readonly T[], favoriteIds: ReadonlySet<number>): T[] {
  return list.slice().sort((a, b) => {
    const aFav = favoriteIds.has(a.fixture_id)
    const bFav = favoriteIds.has(b.fixture_id)
    if (aFav !== bFav) return aFav ? -1 : 1
    return (
      parseApiDate(a.fixture_date).getTime() -
      parseApiDate(b.fixture_date).getTime()
    )
  })
}
