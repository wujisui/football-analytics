/** Detail「我的预测」右侧：由盘口 + 算法倾向生成的解释文案（非主观因素融合）。 */

import type { AnalysisResponse, MatchWinnerOdds, OddsPackage } from '@/api/types'
import { ahLinesOf } from '@/utils/oddsDisplay'

export type PredictionExplanation = {
  title: string
  paragraphs: string[]
  bullets: string[]
}

type Side = 'home' | 'draw' | 'away'

function parseOdd(value: string | number | null | undefined): number | null {
  if (value == null || value === '') return null
  const n = typeof value === 'number' ? value : Number(String(value).trim())
  return Number.isFinite(n) && n > 1 ? n : null
}

/** Remove overround and return normalized 1X2 implied probs. */
function implied1x2(mw: MatchWinnerOdds | null | undefined): {
  home: number
  draw: number
  away: number
} | null {
  if (!mw) return null
  const h = parseOdd(mw.home)
  const d = parseOdd(mw.draw)
  const a = parseOdd(mw.away)
  if (h == null || d == null || a == null) return null
  const rawH = 1 / h
  const rawD = 1 / d
  const rawA = 1 / a
  const sum = rawH + rawD + rawA
  if (!(sum > 0)) return null
  return { home: rawH / sum, draw: rawD / sum, away: rawA / sum }
}

function sideLabel(side: Side): string {
  if (side === 'home') return '主胜'
  if (side === 'draw') return '平局'
  return '客胜'
}

function topSide(probs: { home: number; draw: number; away: number }): Side {
  if (probs.home >= probs.draw && probs.home >= probs.away) return 'home'
  if (probs.away >= probs.draw && probs.away >= probs.home) return 'away'
  return 'draw'
}

function pct(p: number): string {
  return `${Math.round(p * 100)}%`
}

function recMentions(side: Side, recommendation: string): boolean {
  const r = recommendation || ''
  if (side === 'home') return /主胜|主队/.test(r) && !/主负|客胜/.test(r)
  if (side === 'away') return /客胜|主负/.test(r)
  return /平/.test(r)
}

function oddDeltaText(
  open: number | null,
  curr: number | null,
  label: string,
): string | null {
  if (open == null || curr == null) return null
  const d = curr - open
  if (Math.abs(d) < 0.05) return null
  if (d < 0) return `${label}赔率从 ${open} 降到 ${curr}，市场热度上升`
  return `${label}赔率从 ${open} 升到 ${curr}，市场热度回落`
}

/**
 * Build explanation copy for the detail prediction compare right panel.
 * Uses already-normalized leans + odds; no extra display decoration.
 */
export function buildPredictionExplanation(
  analysis: AnalysisResponse,
): PredictionExplanation {
  const paragraphs: string[] = []
  const bullets: string[] = []
  const odds = (analysis.package?.odds ?? null) as OddsPackage | null
  const opening = (analysis.package?.odds_opening ?? null) as OddsPackage | null
  const currentImp = implied1x2(odds?.match_winner)
  const openImp = implied1x2(opening?.match_winner)
  const rec = (analysis.recommendation || '').trim() || '待分析'

  if (currentImp) {
    const fav = topSide(currentImp)
    const favP = currentImp[fav]
    paragraphs.push(
      `即时盘隐含概率更偏向${sideLabel(fav)}（约 ${pct(favP)}）：主 ${pct(currentImp.home)} / 平 ${pct(currentImp.draw)} / 客 ${pct(currentImp.away)}。这大致对应市场共识下庄家更需防范的一侧。`,
    )

    if (rec !== '待分析') {
      if (recMentions(fav, rec)) {
        paragraphs.push(
          `算法推荐「${rec}」与盘口倾向一致，当前结论可看作市场基线与本地模型同向。`,
        )
      } else {
        paragraphs.push(
          `算法推荐「${rec}」，与盘口更看好的「${sideLabel(fav)}」不完全同向；若跟盘，需接受和市场热门方向不一致的风险。`,
        )
      }
    }
  } else if (rec !== '待分析') {
    paragraphs.push(`暂无完整胜平负盘口，当前算法推荐为「${rec}」。`)
  } else {
    paragraphs.push('暂缺可用盘口与有效推荐，待赛前数据补齐后再解读。')
  }

  if (openImp && currentImp) {
    const openFav = topSide(openImp)
    const currFav = topSide(currentImp)
    if (openFav !== currFav) {
      paragraphs.push(
        `相对初盘，市场热门方向由「${sideLabel(openFav)}」转向「${sideLabel(currFav)}」，临场资金偏好有变化。`,
      )
    }
  }

  const mwOpen = opening?.match_winner
  const mwCurr = odds?.match_winner
  if (mwOpen && mwCurr) {
    for (const [label, key] of [
      ['主胜', 'home'],
      ['平局', 'draw'],
      ['客胜', 'away'],
    ] as const) {
      const line = oddDeltaText(
        parseOdd(mwOpen[key]),
        parseOdd(mwCurr[key]),
        label,
      )
      if (line) bullets.push(line)
    }
  }

  const ah = ahLinesOf(odds?.asian_handicap)[0]
  const ahLean = (analysis.handicap_lean || '').trim()
  if (ahLean && ahLean !== '让球:待分析') {
    const line = ah?.line != null ? `（主盘 ${ah.line}）` : ''
    bullets.push(`让球倾向：${ahLean}${line}`)
  }

  const goal = (analysis.goal_lean || '').trim()
  if (goal && !goal.includes('待分析')) {
    const ou = odds?.goals_ou
    const line = ou?.line != null ? `（盘口 ${ou.line}）` : ''
    bullets.push(`大小球：${goal}${line}`)
  }

  const btts = (analysis.both_score_lean || '').trim()
  if (btts && !btts.includes('待分析')) {
    bullets.push(`双方进球：${btts}`)
  }

  const score = (analysis.score_hint || '').trim()
  if (score && !score.includes('待分析')) {
    bullets.push(`参考比分：${score}`)
  }

  if (analysis.confidence) {
    bullets.push(`置信度标注：${analysis.confidence}`)
  }

  const source = (analysis.data_source || '').trim()
  if (source) {
    bullets.push(`数据来源：${source}`)
  }

  return {
    title: '盘口解释',
    paragraphs,
    bullets,
  }
}
