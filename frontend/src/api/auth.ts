import { apiClient } from './client'

export type UserRole = 'system_admin' | 'ops_admin' | 'user' | 'vip'

export const USER_ROLE_LABEL: Record<UserRole, string> = {
  system_admin: '系统管理员',
  ops_admin: '运维管理员',
  user: '普通用户',
  vip: 'VIP',
}

export function isUserRole(value: unknown): value is UserRole {
  return value === 'system_admin'
    || value === 'ops_admin'
    || value === 'user'
    || value === 'vip'
}

export interface AuthUser {
  id: string
  username: string
  role: UserRole
  league_default_ids: number[] | null
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

export async function saveLeagueDefaults(leagueIds: number[]): Promise<AuthUser> {
  const { data } = await apiClient.put<AuthUser>('/auth/me/league-defaults', {
    league_ids: leagueIds,
  })
  return data
}
