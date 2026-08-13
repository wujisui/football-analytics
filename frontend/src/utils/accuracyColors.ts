export const ACCURACY_COLORS = {
  result: '#d03050',
  autoPick: '#0e7a8a',
  score: '#2080f0',
  ou: '#f0a020',
  btts: '#18a058',
  handicap: '#8a2be2',
} as const

/** Day-stats / history metric card colors keyed like ResultsHitKey. */
export const ACCURACY_COLOR_BY_HIT_KEY = {
  result: ACCURACY_COLORS.result,
  auto_pick: ACCURACY_COLORS.autoPick,
  score: ACCURACY_COLORS.score,
  ou: ACCURACY_COLORS.ou,
  btts: ACCURACY_COLORS.btts,
  handicap: ACCURACY_COLORS.handicap,
} as const
