import { apiClient } from './client'
import type { LeaguesListResponse } from './types'

export async function fetchLeagues(): Promise<LeaguesListResponse> {
  const { data } = await apiClient.get<LeaguesListResponse>('/leagues')
  return data
}
