import type { ProbabilitiesResponse } from '@/api/types'
import { hasRealProbabilities } from '@/utils/format'

export interface PredictionSnapshot {
  home_win_prob: number
  draw_prob: number
  away_win_prob: number
  recommendation: string
  goal_lean: string
  both_score_lean: string
  score_hint: string
  handicap_lean: string
  probabilitiesAvailable: boolean
}

/** Map analysis payload → snapshot for prediction UI. */
export function snapshotFromAnalysis(analysis: {
  probabilities: ProbabilitiesResponse
  recommendation: string
  goal_lean?: string
  both_score_lean?: string
  score_hint?: string
  handicap_lean?: string
}): PredictionSnapshot {
  const ready = hasRealProbabilities(analysis.probabilities, analysis.recommendation)
  return {
    home_win_prob: ready ? Number(analysis.probabilities.home_win_prob) : 0,
    draw_prob: ready ? Number(analysis.probabilities.draw_prob) : 0,
    away_win_prob: ready ? Number(analysis.probabilities.away_win_prob) : 0,
    recommendation: analysis.recommendation,
    goal_lean: analysis.goal_lean || '',
    both_score_lean: analysis.both_score_lean || '',
    score_hint: analysis.score_hint || '',
    handicap_lean: analysis.handicap_lean || '',
    probabilitiesAvailable: ready,
  }
}
