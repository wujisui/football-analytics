import { computed, ref } from 'vue'

const STORAGE_KEY = 'fa-auth-session'

export type AuthSession = {
  username: string
  loggedInAt: string
}

function readSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<AuthSession>
    if (!parsed?.username || typeof parsed.username !== 'string') return null
    return {
      username: parsed.username.trim(),
      loggedInAt:
        typeof parsed.loggedInAt === 'string'
          ? parsed.loggedInAt
          : new Date().toISOString(),
    }
  } catch {
    return null
  }
}

function writeSession(session: AuthSession | null) {
  try {
    if (!session) localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  } catch {
    /* private mode / quota */
  }
}

const session = ref<AuthSession | null>(readSession())
const loginModalShow = ref(false)

/**
 * Auth session for 「登录 / 我的」.
 * - Mobile: Mine always available; login entry lives on the Mine page.
 * - Desktop: Mine nav only after login; otherwise header shows 登录.
 * Backend auth is not wired yet — credentials are accepted locally.
 */
export function useAuthSession() {
  const isLoggedIn = computed(() => !!session.value)
  const username = computed(() => session.value?.username ?? '')

  function openLogin() {
    loginModalShow.value = true
  }

  function closeLogin() {
    loginModalShow.value = false
  }

  function login(name: string) {
    const username = name.trim()
    if (!username) return false
    const next: AuthSession = {
      username,
      loggedInAt: new Date().toISOString(),
    }
    session.value = next
    writeSession(next)
    loginModalShow.value = false
    return true
  }

  function logout() {
    session.value = null
    writeSession(null)
  }

  return {
    session,
    isLoggedIn,
    username,
    loginModalShow,
    openLogin,
    closeLogin,
    login,
    logout,
  }
}
