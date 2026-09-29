import type { UserRole } from '@/api/auth'

/** VIP account default. Null means "use the site hot default". */
let saved: number[] | null = null

export function setPersonalLeagueDefaults(
  role: UserRole | null,
  ids: number[] | null,
): void {
  saved = role === 'vip' ? ids : null
}

export function personalLeagueDefaults(): number[] | null {
  return saved
}
