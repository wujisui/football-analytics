import { computed, onUnmounted, ref } from 'vue'

import type { SyncFixturesResult } from '@/api/fixtures'

/** Keep in sync with backend `_SYNC_COOLDOWN_SECONDS`. */
export const SYNC_COOLDOWN_SECONDS = 90

/** Shared across Home / Results — backend sync cooldown is process-wide. */
const cooldownLeft = ref(0)
let timer: ReturnType<typeof setInterval> | null = null
let subscribers = 0

function clearTimer() {
  if (timer != null) {
    clearInterval(timer)
    timer = null
  }
}

function tick() {
  if (cooldownLeft.value <= 0) {
    clearTimer()
    return
  }
  cooldownLeft.value -= 1
  if (cooldownLeft.value <= 0) clearTimer()
}

function startCooldown(seconds: number) {
  const sec = Math.max(0, Math.ceil(Number(seconds) || 0))
  cooldownLeft.value = sec
  clearTimer()
  if (sec <= 0) return
  timer = setInterval(tick, 1000)
}

/**
 * Global force-sync cooldown (matches backend ~90s).
 * After any sync response, disable the button until the timer ends.
 */
export function useSyncCooldown() {
  subscribers += 1
  onUnmounted(() => {
    subscribers -= 1
    if (subscribers <= 0) {
      // Keep countdown running in background if another page still mounted;
      // only clear interval when last consumer leaves and already expired.
      if (cooldownLeft.value <= 0) clearTimer()
    }
  })

  const inCooldown = computed(() => cooldownLeft.value > 0)

  /**
   * Apply server sync response: always start local cooldown.
   * @returns true if the request was blocked (already cooling on server)
   */
  function applySyncResult(result: SyncFixturesResult): boolean {
    const seconds =
      result.retry_after_seconds ??
      (result.status === 'cooldown' ? cooldownLeft.value || SYNC_COOLDOWN_SECONDS : SYNC_COOLDOWN_SECONDS)
    startCooldown(seconds)
    return result.status === 'cooldown'
  }

  return {
    cooldownLeft,
    inCooldown,
    startCooldown,
    applySyncResult,
  }
}
