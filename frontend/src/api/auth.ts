import { apiClient } from './client'

export interface AuthUser {
  id: string
  username: string
  is_admin: boolean
}

export interface AuthClaim {
  favorites: number
  favorites_dup_dropped: number
  plans: number
}

/** Login/register result; the session token arrives as an httpOnly cookie. */
export interface AuthSession {
  user: AuthUser
  claimed: AuthClaim
}

export async function registerAccount(
  username: string,
  password: string,
): Promise<AuthSession> {
  const { data } = await apiClient.post<AuthSession>('/auth/register', {
    username,
    password,
  })
  return data
}

export async function loginAccount(
  username: string,
  password: string,
): Promise<AuthSession> {
  const { data } = await apiClient.post<AuthSession>('/auth/login', {
    username,
    password,
  })
  return data
}

export async function logoutAccount(): Promise<void> {
  await apiClient.post('/auth/logout')
}

export async function fetchAuthMe(): Promise<AuthUser> {
  const { data } = await apiClient.get<AuthUser>('/auth/me')
  return data
}
