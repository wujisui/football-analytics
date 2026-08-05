import { apiClient } from './client'
import type { CalcSelection, FoldMode } from '@/utils/betCalculator'

export interface BetPlanDto {
  id: string
  name: string
  saved_at: string
  plan_day: string
  fold: FoldMode | string
  multiplier: number
  selections: CalcSelection[]
}

export interface BetPlansResponse {
  total: number
  plans: BetPlanDto[]
}

export interface BetPlanDaysResponse {
  days: string[]
}

export async function fetchBetPlans(planDay?: string): Promise<BetPlansResponse> {
  const { data } = await apiClient.get<BetPlansResponse>('/bet-plans', {
    params: planDay ? { plan_day: planDay } : undefined,
  })
  return data
}

export async function fetchBetPlanDays(): Promise<string[]> {
  const { data } = await apiClient.get<BetPlanDaysResponse>('/bet-plans/days')
  return data.days
}

export async function fetchBetPlan(planId: string): Promise<BetPlanDto> {
  const { data } = await apiClient.get<BetPlanDto>(`/bet-plans/${planId}`)
  return data
}

export async function createBetPlan(body: {
  name: string
  plan_day: string
  fold: string
  multiplier: number
  selections: CalcSelection[]
  id?: string
}): Promise<BetPlanDto> {
  const { data } = await apiClient.post<BetPlanDto>('/bet-plans', body)
  return data
}

export async function renameBetPlan(planId: string, name: string): Promise<BetPlanDto> {
  const { data } = await apiClient.patch<BetPlanDto>(`/bet-plans/${planId}`, { name })
  return data
}

export async function deleteBetPlan(planId: string): Promise<void> {
  await apiClient.delete(`/bet-plans/${planId}`)
}
