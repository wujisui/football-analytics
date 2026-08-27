import { computed, ref } from 'vue'

import {
  fetchAuthMe,
  loginAccount,
  logoutAccount,
  registerAccount,
  type AuthClaim,
} from '@/api/auth'
import { clearAdminSettingsCache } from '@/api/admin'
import { setOnAuthExpired, type ApiError } from '@/api/client'
import {
  clearPrivateBetPlans,
  useBetPlans,
} from '@/composables/useBetPlans'
import {
  clearPrivateFavorites,
  useFavoriteFixtures,
} from '@/composables/useFavoriteFixtures'
import { clearPrivateCalculator } from '@/views/Predictions/composables/useBetCalculator'

/**
 * Cached display identity only — the session itself is an httpOnly cookie that
 * scripts cannot read, so this is a paint hint that `verifySession` confirms.
 */
const STORAGE_KEY = 'fa-auth-user'

export type AuthUserCache = {
  userId: string
  username: string
  isAdmin: boolean
}

function readCachedUser(): AuthUserCache | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<AuthUserCache>
    if (!parsed?.username || typeof parsed.username !== 'string') return null
    return {
      userId: typeof parsed.userId === 'string' ? parsed.userId : '',
      username: parsed.username.trim(),
      isAdmin: !!parsed.isAdmin,
    }
  } catch {
    return null
  }
}

function writeCachedUser(user: AuthUserCache | null) {
  try {
    if (!user) localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
  } catch {
    /* private mode / quota */
  }
}

const user = ref<AuthUserCache | null>(readCachedUser())
const loginModalShow = ref(false)

function clearLocalUser() {
  user.value = null
  writeCachedUser(null)
}

/**
 * Drop account-scoped client caches. Keeps device prefs (theme, league filters,
 * remember-account, date strips, scroll).
 */
function wipePrivateClientCaches() {
  clearAdminSettingsCache()
  clearPrivateBetPlans()
  clearPrivateFavorites()
  clearPrivateCalculator()
}

async function refreshPrivateCaches(mode: 'guest' | 'user') {
  wipePrivateClientCaches()
  const { refresh: refreshFavorites } = useFavoriteFixtures()
  if (mode === 'guest') {
    // Guest may still see shared daily auto tips; plans stay empty until login.
    await Promise.allSettled([refreshFavorites()])
    return
  }
  const { reload: reloadPlans } = useBetPlans()
  await Promise.allSettled([refreshFavorites(), reloadPlans()])
}

setOnAuthExpired(() => {
  clearLocalUser()
  void refreshPrivateCaches('guest')
})

/**
 * Auth session for 「登录 / 我的」.
 * Backend: httpOnly `fa_session` cookie set by `/auth/login` / `/auth/register`.
 */
export function useAuthSession() {
  const isLoggedIn = computed(() => !!user.value)
  const username = computed(() => user.value?.username ?? '')
  const isAdmin = computed(() => !!user.value?.isAdmin)

  function openLogin() {
    loginModalShow.value = true
  }

  function closeLogin() {
    loginModalShow.value = false
  }

  /** Private writes (收藏 / 方案). Opens the login modal and returns false when guest. */
  function requireLogin(): boolean {
    if (user.value) return true
    loginModalShow.value = true
    return false
  }

  function applyUser(userId: string, name: string, isAdminFlag: boolean) {
    const next: AuthUserCache = {
      userId,
      username: name,
      isAdmin: !!isAdminFlag,
    }
    user.value = next
    writeCachedUser(next)
  }

  async function submit(
    kind: 'login' | 'register',
    name: string,
    password: string,
  ): Promise<{ ok: true; claimed: AuthClaim } | { ok: false; error: string }> {
    const account = name.trim()
    if (!account || !password) {
      return { ok: false, error: '请输入账号和密码' }
    }
    try {
      const data =
        kind === 'register'
          ? await registerAccount(account, password)
          : await loginAccount(account, password)
      applyUser(data.user.id, data.user.username, data.user.is_admin)
      loginModalShow.value = false
      await refreshPrivateCaches('user')
      return { ok: true, claimed: data.claimed }
    } catch (err) {
      const fallback = kind === 'register' ? '注册失败' : '登录失败'
      return {
        ok: false,
        error: err instanceof Error ? err.message : fallback,
      }
    }
  }

  function login(name: string, password: string) {
    return submit('login', name, password)
  }

  function register(name: string, password: string) {
    return submit('register', name, password)
  }

  async function logout() {
    try {
      await logoutAccount()
    } catch {
      /* still clear local state */
    }
    clearLocalUser()
    await refreshPrivateCaches('guest')
  }

  /** Confirm the cookie is still valid once after boot (401 → guest). */
  async function verifySession() {
    if (!user.value) return
    try {
      const me = await fetchAuthMe()
      applyUser(me.id, me.username, me.is_admin)
    } catch (err) {
      // Only an explicit 401 means the session is gone; a network error or a
      // stopped backend must not silently log the user out.
      if ((err as ApiError)?.status !== 401) return
      clearLocalUser()
      await refreshPrivateCaches('guest')
    }
  }

  return {
    user,
    isLoggedIn,
    isAdmin,
    username,
    loginModalShow,
    openLogin,
    closeLogin,
    requireLogin,
    login,
    register,
    logout,
    verifySession,
  }
}
