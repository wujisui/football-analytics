/** Backend serves translated `league_name`; display as-is. */
export function leagueLabel(name?: string | null): string {
  return (name || '').trim()
}
