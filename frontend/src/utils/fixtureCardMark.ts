/** Shared click-to-mark helpers for fixture list cards (赛果 / 比赛 / 关注). */

/** Controls that own their own click semantics — ignore for reading marks. */
export const FIXTURE_CARD_MARK_IGNORE =
  'button, a, input, textarea, select, [role="button"], .n-tag, .n-rate, .n-checkbox'

export function isFixtureCardMarkClickIgnored(event: Event): boolean {
  const el = event.target as Element | null
  return !!el?.closest(FIXTURE_CARD_MARK_IGNORE)
}
