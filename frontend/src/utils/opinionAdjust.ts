import type { ProbabilitiesResponse } from '@/api/types'

export interface PredictionSnapshot {
  home_win_prob: number
  draw_prob: number
  away_win_prob: number
  recommendation: string
  /** Heuristic lean from 1X2 probs — not an official O/U market. */
  goal_lean: string
  both_score_lean: string
  score_hint: string
}

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n))
}

function normalize(home: number, draw: number, away: number): ProbabilitiesResponse {
  const sum = home + draw + away
  if (sum <= 0) {
    return { home_win_prob: 1 / 3, draw_prob: 1 / 3, away_win_prob: 1 / 3 }
  }
  return {
    home_win_prob: home / sum,
    draw_prob: draw / sum,
    away_win_prob: away / sum,
  }
}

function recommendationFrom(probs: ProbabilitiesResponse): string {
  const { home_win_prob: h, draw_prob: d, away_win_prob: a } = probs
  if (h >= d && h >= a) return '主胜'
  if (a >= d && a >= h) return '客胜'
  return '平局'
}

function goalLean(probs: ProbabilitiesResponse): string {
  const spread = Math.abs(probs.home_win_prob - probs.away_win_prob)
  const drawHeavy = probs.draw_prob >= 0.3
  if (drawHeavy && spread < 0.12) return '小球倾向（约 2.5）'
  if (Math.max(probs.home_win_prob, probs.away_win_prob) >= 0.5) {
    return '大球倾向（约 2.5）'
  }
  return '大小球接近（约 2.5）'
}

function bothScoreLean(probs: ProbabilitiesResponse): string {
  const favorite = Math.max(probs.home_win_prob, probs.away_win_prob)
  if (favorite >= 0.55 && probs.draw_prob < 0.25) return '双方进球：倾向否'
  if (probs.draw_prob >= 0.28 || favorite < 0.45) return '双方进球：倾向是'
  return '双方进球：中性'
}

function scoreHint(probs: ProbabilitiesResponse): string {
  const rec = recommendationFrom(probs)
  if (rec === '主胜') {
    return probs.home_win_prob >= 0.55 ? '2-1' : '1-0'
  }
  if (rec === '客胜') {
    return probs.away_win_prob >= 0.55 ? '1-2' : '0-1'
  }
  return probs.draw_prob >= 0.35 ? '1-1' : '0-0'
}

export function toPredictionSnapshot(
  probabilities: ProbabilitiesResponse,
  recommendation?: string,
): PredictionSnapshot {
  const probs = normalize(
    probabilities.home_win_prob,
    probabilities.draw_prob,
    probabilities.away_win_prob,
  )
  return {
    ...probs,
    recommendation: recommendation || recommendationFrom(probs),
    goal_lean: goalLean(probs),
    both_score_lean: bothScoreLean(probs),
    score_hint: scoreHint(probs),
  }
}

/**
 * Local-only fusion: nudge algorithm probs from subjective text cues.
 * Backend has no /predict yet — this is a transparent client heuristic.
 */
export function adjustWithOpinion(
  base: ProbabilitiesResponse,
  opinion: string,
): PredictionSnapshot {
  let home = base.home_win_prob
  let draw = base.draw_prob
  let away = base.away_win_prob
  const text = opinion.trim()

  if (!text) {
    return toPredictionSnapshot(base)
  }

  const lower = text.toLowerCase()

  // Directional cues
  if (/客胜|客队更强|客队占优|客队有利|away/.test(text) || /客队.*(优势|更强)/.test(text)) {
    away += 0.08
    home -= 0.05
    draw -= 0.03
  } else if (/主胜|主队更强|主队占优|主队有利|home/.test(text) || /主队.*(优势|更强)/.test(text)) {
    home += 0.08
    away -= 0.05
    draw -= 0.03
  }

  if (/平局|握手言和|打平|draw/.test(text)) {
    draw += 0.07
    home -= 0.035
    away -= 0.035
  }

  // Form / fitness / injury cues
  if (/主队.*(伤|停|缺阵|体能|疲劳|密集)/.test(text) || /主队.*(伤病|伤停)/.test(text)) {
    home -= 0.06
    away += 0.03
    draw += 0.03
  }
  if (/客队.*(伤|停|缺阵|体能|疲劳|密集)/.test(text) || /客队.*(伤病|伤停)/.test(text)) {
    away -= 0.06
    home += 0.03
    draw += 0.03
  }
  if (/主队.*(复出|状态好|状态出色|火力)/.test(text)) {
    home += 0.04
    away -= 0.02
    draw -= 0.02
  }
  if (/客队.*(复出|状态好|状态出色|火力)/.test(text)) {
    away += 0.04
    home -= 0.02
    draw -= 0.02
  }

  // Goal market cues (affect lean via probs)
  if (/大球|进球多|对攻|高比分|over/.test(lower) || /大球/.test(text)) {
    draw -= 0.03
    home += 0.015
    away += 0.015
  }
  if (/小球|闷平|防守|低比分|under/.test(lower) || /小球/.test(text)) {
    draw += 0.05
    home -= 0.025
    away -= 0.025
  }

  home = clamp(home, 0.05, 0.85)
  draw = clamp(draw, 0.05, 0.7)
  away = clamp(away, 0.05, 0.85)

  return toPredictionSnapshot(normalize(home, draw, away))
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
  return keys
}
