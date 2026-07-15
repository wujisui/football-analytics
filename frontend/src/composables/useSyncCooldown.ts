import { computed, onUnmounted, ref, watch } from 'vue'

import type { SyncFixturesResult } from '@/api/fixtures'

/** Keep in sync with backend `_SYNC_COOLDOWN_SECONDS`. */
export const SYNC_COOLDOWN_SECONDS = 90

const STORAGE_KEY = 'fa_sync_cooldown_enabled'

function readCooldownEnabled(): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === null) return true
    return raw !== '0' && raw !== 'false'
  } catch {
    return true
  }
}

/** Shared across Home / Results — backend sync cooldown is process-wide. */
const cooldownLeft = ref(0)
/** When false, sync buttons ignore local + server cooldown (quota risk). */
const cooldownEnabled = ref(readCooldownEnabled())
let timer: ReturnType<typeof setInterval> | null = null
let subscribers = 0

watch(cooldownEnabled, (on) => {
  try {
    localStorage.setItem(STORAGE_KEY, on ? '1' : '0')
  } catch {
    /* ignore quota / private mode */
  }
})

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
 * Toggle ``cooldownEnabled`` off to allow rapid sync (still hits official API).
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

  const inCooldown = computed(
    () => cooldownEnabled.value && cooldownLeft.value > 0,
  )

  /**
   * Apply server sync response: start local cooldown when protection is on.
   * @returns true if the request was blocked (already cooling on server)
   */
  function applySyncResult(result: SyncFixturesResult): boolean {
    const blocked = result.status === 'cooldown'
    if (!cooldownEnabled.value) {
      if (!blocked) cooldownLeft.value = 0
      return blocked
    }
    const seconds =
      result.retry_after_seconds ??
      (blocked ? cooldownLeft.value || SYNC_COOLDOWN_SECONDS : SYNC_COOLDOWN_SECONDS)
    startCooldown(seconds)
    return blocked
  }

  function setCooldownEnabled(on: boolean) {
    cooldownEnabled.value = on
  }

  return {
    cooldownLeft,
    cooldownEnabled,
    setCooldownEnabled,
    inCooldown,
    applySyncResult,
  }
}
