import { computed, onUnmounted, ref } from 'vue'

import type { SyncFixturesResult } from '@/api/fixtures'

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
 * Shows remaining seconds so users do not keep clicking blindly.
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

  const cooldownHint = computed(() => {
    if (cooldownLeft.value <= 0) return ''
    return `同步冷却中，请 ${cooldownLeft.value} 秒后再试（保护官方 API 配额）`
  })

  function applySyncResult(result: SyncFixturesResult): boolean {
    if (result.status !== 'cooldown') return false
    const retry = result.retry_after_seconds ?? 90
    startCooldown(retry)
    return true
  }

  return {
    cooldownLeft,
    inCooldown,
    cooldownHint,
    startCooldown,
    applySyncResult,
  }
}
