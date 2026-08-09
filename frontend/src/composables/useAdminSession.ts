import { computed, ref } from 'vue'

const STORAGE_KEY = 'fa-admin-key'

function readStored(): string {
  try {
    return (localStorage.getItem(STORAGE_KEY) || '').trim()
  } catch {
    return ''
  }
}

const adminKey = ref(readStored())

export function useAdminSession() {
  const hasAdminKey = computed(() => adminKey.value.length > 0)

  function setAdminKey(key: string) {
    const next = key.trim()
    adminKey.value = next
    try {
      if (next) localStorage.setItem(STORAGE_KEY, next)
      else localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* ignore */
    }
  }

  function clearAdminKey() {
    setAdminKey('')
  }

  return {
    adminKey,
    hasAdminKey,
    setAdminKey,
    clearAdminKey,
  }
}
