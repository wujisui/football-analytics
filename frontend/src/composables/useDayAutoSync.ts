/** Dates already auto-synced this browser session (incl. confirmed empty days). */
const autoSyncedDates = new Set<string>()
/** Dates already attempted odds gap-fill this session. */
const oddsGapFillDates = new Set<string>()

export function isDayAutoSynced(date: string): boolean {
  return autoSyncedDates.has(date)
}

export function markDayAutoSynced(date: string): void {
  autoSyncedDates.add(date)
}

export function shouldGapFillOdds(date: string): boolean {
  return !oddsGapFillDates.has(date)
}

export function markOddsGapFillTried(date: string): void {
  oddsGapFillDates.add(date)
}

export function clearOddsGapFillTried(date: string): void {
  oddsGapFillDates.delete(date)
}

/** Skip official sync when session already tried, or local DB already has rows for the day. */
export function shouldAutoSyncDay(date: string, localHasData: boolean): boolean {
  if (isDayAutoSynced(date)) return false
  if (localHasData) {
    markDayAutoSynced(date)
    return false
  }
  return true
}
