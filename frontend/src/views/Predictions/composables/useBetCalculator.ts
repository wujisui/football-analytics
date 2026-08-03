import { computed, ref, watch } from 'vue'

import type { FixtureResponse } from '@/api/types'
import {
  availableFoldModes,
  calculateParlay,
  foldModeLabel,
  MAX_CALC_MATCHES,
  MAX_SPF_PICKS,
  selectedFixtureIds,
  type CalcCell,
  type CalcSelection,
  type FoldMode,
} from '@/utils/betCalculator'
import { formatDate, formatTime } from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'

const selections = ref<CalcSelection[]>([])
const multiplier = ref(1)
const fold = ref<FoldMode>('2x1')

export type GroupedFixtureSelections = {
  fixtureId: number
  leagueId: number
  picks: CalcSelection[]
  homeName: string
  awayName: string
  kickoff: string
  leagueName: string
}

export function useBetCalculator() {
  const matchCount = computed(() => selectedFixtureIds(selections.value).length)

  const foldOptions = computed(() =>
    availableFoldModes(matchCount.value).map((mode) => ({
      label: foldModeLabel(mode),
      value: mode,
    })),
  )

  // 选中场次变化后默认取最大过关方式（N 场 → N串1），用户仍可手动降档
  watch(matchCount, (n) => {
    const modes = availableFoldModes(n)
    if (!modes.length) return
    fold.value = modes[modes.length - 1]
  })

  const result = computed(() =>
    calculateParlay(selections.value, fold.value, multiplier.value),
  )

  function isSelected(fixtureId: number, cell: CalcCell): boolean {
    return selections.value.some(
      (s) =>
        s.fixtureId === fixtureId
        && s.market === cell.market
        && s.outcome === cell.outcome,
    )
  }

  function toggleCell(fixture: FixtureResponse, cell: CalcCell): string | null {
    if (cell.disabled || cell.odd == null) {
      return cell.disabledReason || '暂无赔率'
    }

    const fixtureId = fixture.fixture_id
    const existingIdx = selections.value.findIndex(
      (s) =>
        s.fixtureId === fixtureId
        && s.market === cell.market
        && s.outcome === cell.outcome,
    )
    // 再点已选项 → 取消
    if (existingIdx >= 0) {
      selections.value = selections.value.filter((_, i) => i !== existingIdx)
      return null
    }

    const ids = selectedFixtureIds(selections.value)
    if (!ids.includes(fixtureId) && ids.length >= MAX_CALC_MATCHES) {
      return `最多选择 ${MAX_CALC_MATCHES} 场`
    }

    // 冲突项直接让位：换玩法清掉本场其它玩法；同玩法按规则替换
    let next = selections.value.filter((s) => {
      if (s.fixtureId !== fixtureId) return true
      if (s.market !== cell.market) return false
      // 让球 / 大小：同玩法只留新点的一项
      if (cell.market !== 'spf') return false
      return true
    })

    if (cell.market === 'spf') {
      const spfPicks = next.filter(
        (s) => s.fixtureId === fixtureId && s.market === 'spf',
      )
      // 已满双选时再点第三项：清掉本场胜平负，只保留当前点击
      if (spfPicks.length >= MAX_SPF_PICKS) {
        next = next.filter(
          (s) => !(s.fixtureId === fixtureId && s.market === 'spf'),
        )
      }
    }

    next.push({
      fixtureId,
      leagueId: fixture.league_id,
      homeName: fixture.home_team_name || '—',
      awayName: fixture.away_team_name || '—',
      kickoff: `${formatDate(fixture.fixture_date)} ${formatTime(fixture.fixture_date)}`,
      leagueName: leagueLabel(fixture.league_name),
      market: cell.market,
      outcome: cell.outcome,
      playLabel: cell.playLabel,
      pickLabel: cell.pickLabel,
      odd: cell.odd,
      line: cell.line,
    })
    selections.value = next
    return null
  }

  function clearAll() {
    selections.value = []
  }

  function removeFixture(fixtureId: number) {
    selections.value = selections.value.filter((s) => s.fixtureId !== fixtureId)
  }

  /** Group selections by fixture for the bet details panel. */
  const groupedSelections = computed((): GroupedFixtureSelections[] => {
    const map = new Map<number, CalcSelection[]>()
    for (const sel of selections.value) {
      const list = map.get(sel.fixtureId) ?? []
      list.push(sel)
      map.set(sel.fixtureId, list)
    }
    return [...map.entries()].map(([fixtureId, picks]) => ({
      fixtureId,
      leagueId: picks[0].leagueId,
      picks,
      homeName: picks[0].homeName,
      awayName: picks[0].awayName,
      kickoff: picks[0].kickoff,
      leagueName: picks[0].leagueName,
    }))
  })

  return {
    multiplier,
    fold,
    matchCount,
    foldOptions,
    result,
    groupedSelections,
    isSelected,
    toggleCell,
    clearAll,
    removeFixture,
  }
}
