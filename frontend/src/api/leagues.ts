import { apiClient } from './client'
import type { LeaguesListResponse } from './types'

export async function fetchLeagues(params?: {
  date?: string
  days?: number
}): Promise<LeaguesListResponse> {
  const { data } = await apiClient.get<LeaguesListResponse>('/leagues', { params })
  return data
}
