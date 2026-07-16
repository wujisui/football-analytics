/** Dates already auto-synced this browser session (incl. confirmed empty days). */
const autoSyncedDates = new Set<string>()

export function isDayAutoSynced(date: string): boolean {
  return autoSyncedDates.has(date)
}

export function markDayAutoSynced(date: string): void {
  autoSyncedDates.add(date)
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
