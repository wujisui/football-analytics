export interface PredictionSnapshot {
  home_win_prob: number
  draw_prob: number
  away_win_prob: number
  recommendation: string
  goal_lean: string
  both_score_lean: string
  score_hint: string
  handicap_lean: string
}

export function predictionDiffKeys(
  original: PredictionSnapshot,
  adjusted: PredictionSnapshot,
): Set<string> {
  const keys = new Set<string>()
  if (original.recommendation !== adjusted.recommendation) keys.add('recommendation')
  if (Math.abs(original.home_win_prob - adjusted.home_win_prob) >= 0.01) keys.add('home')
  if (Math.abs(original.draw_prob - adjusted.draw_prob) >= 0.01) keys.add('draw')
  if (Math.abs(original.away_win_prob - adjusted.away_win_prob) >= 0.01) keys.add('away')
  if (original.goal_lean !== adjusted.goal_lean) keys.add('goal_lean')
  if (original.both_score_lean !== adjusted.both_score_lean) keys.add('both_score')
  if (original.score_hint !== adjusted.score_hint) keys.add('score')
  if (original.handicap_lean !== adjusted.handicap_lean) keys.add('handicap')
  return keys
}

/** Map analysis payload → snapshot for compare UI. */
export function snapshotFromAnalysis(analysis: {
  probabilities: {
    home_win_prob: number
    draw_prob: number
    away_win_prob: number
  }
  recommendation: string
  goal_lean?: string
  both_score_lean?: string
  score_hint?: string
  handicap_lean?: string
}): PredictionSnapshot {
  return {
    home_win_prob: analysis.probabilities.home_win_prob,
    draw_prob: analysis.probabilities.draw_prob,
    away_win_prob: analysis.probabilities.away_win_prob,
    recommendation: analysis.recommendation,
    goal_lean: analysis.goal_lean || '',
    both_score_lean: analysis.both_score_lean || '',
    score_hint: analysis.score_hint || '',
    handicap_lean: analysis.handicap_lean || '',
  }
}
