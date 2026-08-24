import { hasKickedOff, parseApiDate } from '@/utils/format'

const FINISHED_SHORT = new Set(['FT', 'AET', 'PEN'])

/** In-play, or kicked off while the local board is still pending. */
export function isInPlayFixture(fixture: {
  status?: string | null
  status_short?: string | null
  fixture_date?: string | null
}): boolean {
  const short = (fixture.status_short || '').toUpperCase()
  if (FINISHED_SHORT.has(short)) return false
  const status = (fixture.status || '').toLowerCase()
  if (
    status === 'finished' ||
    status === 'postponed' ||
    status === 'cancelled' ||
    status === 'canceled'
  ) {
    return false
  }
  if (status === 'live') return true
  return status === 'pending' && hasKickedOff(fixture.fixture_date)
}

/** Live first, then daily picks, then favorites, then kickoff time. */
export function sortFixturesFavoritesFirst<
  T extends {
    fixture_id: number
    fixture_date: string
    status?: string | null
    status_short?: string | null
  },
>(
  list: readonly T[],
  favoriteIds: ReadonlySet<number>,
  dailyPickIds: ReadonlySet<number> = new Set(),
): T[] {
  return list.slice().sort((a, b) => {
    const aLive = isInPlayFixture(a)
    const bLive = isInPlayFixture(b)
    if (aLive !== bLive) return aLive ? -1 : 1
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
