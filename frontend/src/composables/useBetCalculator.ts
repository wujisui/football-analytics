import { computed, ref, watch } from 'vue'

import type { FixtureResponse } from '@/api/types'
import {
  availableFoldModes,
  calculateParlay,
  conflictWithExisting,
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

  function cellBlockedReason(
    fixture: FixtureResponse,
    cell: CalcCell,
  ): string | null {
    if (cell.disabled) return cell.disabledReason || '暂无赔率'
    if (isSelected(fixture.fixture_id, cell)) return null
    const ids = selectedFixtureIds(selections.value)
    if (
      !ids.includes(fixture.fixture_id)
      && ids.length >= MAX_CALC_MATCHES
    ) {
      return `最多选择 ${MAX_CALC_MATCHES} 场`
    }
    const sameMatch = selections.value.filter(
      (s) => s.fixtureId === fixture.fixture_id,
    )
    if (sameMatch.length && sameMatch.every((s) => s.market !== cell.market)) {
      return '每场只能选择一种玩法，请先取消当前选项'
    }
    if (cell.market === 'spf') {
      const spfCount = sameMatch.filter((s) => s.market === 'spf').length
      if (spfCount >= MAX_SPF_PICKS) {
        return '胜平负最多双选'
      }
    }
    return conflictWithExisting(selections.value, fixture.fixture_id, cell)
  }

  function toggleCell(fixture: FixtureResponse, cell: CalcCell): string | null {
    if (cell.disabled || cell.odd == null) {
      return cell.disabledReason || '暂无赔率'
    }

    const existingIdx = selections.value.findIndex(
      (s) =>
        s.fixtureId === fixture.fixture_id
        && s.market === cell.market
        && s.outcome === cell.outcome,
    )
    if (existingIdx >= 0) {
      selections.value = selections.value.filter((_, i) => i !== existingIdx)
      return null
    }

    const blocked = cellBlockedReason(fixture, cell)
    if (blocked) return blocked

    let next: CalcSelection[]
    if (cell.market === 'spf') {
      // 双选：保留同场已选的其它胜平负项
      next = selections.value.slice()
    } else {
      // 让球 / 大小：同玩法替换
      next = selections.value.filter(
        (s) =>
          !(s.fixtureId === fixture.fixture_id && s.market === cell.market),
      )
    }

    next.push({
      fixtureId: fixture.fixture_id,
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
  const groupedSelections = computed(() => {
    const map = new Map<number, CalcSelection[]>()
    for (const sel of selections.value) {
      const list = map.get(sel.fixtureId) ?? []
      list.push(sel)
      map.set(sel.fixtureId, list)
    }
    return [...map.entries()].map(([fixtureId, picks]) => ({
      fixtureId,
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
    cellBlockedReason,
    toggleCell,
    clearAll,
    removeFixture,
  }
}
