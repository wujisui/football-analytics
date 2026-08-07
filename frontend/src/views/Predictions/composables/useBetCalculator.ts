import { computed, ref, watch } from 'vue'

import type { FixtureResponse } from '@/api/types'
import {
  availableFoldModes,
  calculateParlay,
  foldModeLabel,
  allowsDualSelect,
  MAX_CALC_MATCHES,
  MAX_WDL_PICKS,
  selectedFixtureIds,
  type CalcCell,
  type CalcMarket,
  type CalcOutcome,
  type CalcSelection,
  type FoldMode,
} from '@/utils/betCalculator'
import { formatDate, formatTime } from '@/utils/format'
import { leagueLabel } from '@/utils/leagueNames'

/** Survive tab discard / cold reload within the same browser session. */
const STORAGE_KEY = 'fa-bet-calculator'

type StoredBetState = {
  selections: CalcSelection[]
  multiplier: number
  fold: FoldMode
}

const MARKETS = new Set<CalcMarket>(['spf', 'ah', 'ou', 'btts'])
const OUTCOMES = new Set<CalcOutcome>([
  'home',
  'draw',
  'away',
  'over',
  'under',
  'yes',
  'no',
])

function isCalcSelection(raw: unknown): raw is CalcSelection {
  if (!raw || typeof raw !== 'object') return false
  const s = raw as Record<string, unknown>
  return (
    typeof s.fixtureId === 'number' &&
    typeof s.leagueId === 'number' &&
    typeof s.homeName === 'string' &&
    typeof s.awayName === 'string' &&
    typeof s.kickoff === 'string' &&
    typeof s.leagueName === 'string' &&
    MARKETS.has(s.market as CalcMarket) &&
    OUTCOMES.has(s.outcome as CalcOutcome) &&
    typeof s.playLabel === 'string' &&
    typeof s.pickLabel === 'string' &&
    typeof s.odd === 'number' &&
    Number.isFinite(s.odd) &&
    (s.fixtureDate == null || typeof s.fixtureDate === 'string')
  )
}

function readStored(): StoredBetState | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw) as Partial<StoredBetState>
    if (!Array.isArray(data.selections)) return null
    const selections = data.selections.filter(isCalcSelection)
    const multiplier =
      typeof data.multiplier === 'number' &&
      Number.isFinite(data.multiplier) &&
      data.multiplier >= 1
        ? Math.floor(data.multiplier)
        : 1
    const matchCount = selectedFixtureIds(selections).length
    const modes = availableFoldModes(matchCount)
    const fold =
      typeof data.fold === 'string' && modes.includes(data.fold as FoldMode)
        ? (data.fold as FoldMode)
        : modes[modes.length - 1] ?? '2x1'
    return { selections, multiplier, fold }
  } catch {
    return null
  }
}

function writeStored(state: StoredBetState) {
  try {
    if (!state.selections.length && state.multiplier === 1) {
      sessionStorage.removeItem(STORAGE_KEY)
      return
    }
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    /* private mode / quota */
  }
}

const stored = readStored()
const selections = ref<CalcSelection[]>(stored?.selections ?? [])
const multiplier = ref(stored?.multiplier ?? 1)
const fold = ref<FoldMode>(stored?.fold ?? '2x1')

const matchCount = computed(() => selectedFixtureIds(selections.value).length)

// 选中场次变化后默认取最大过关方式（N 场 → N串1），用户仍可手动降档
watch(matchCount, (n) => {
  const modes = availableFoldModes(n)
  if (!modes.length) return
  fold.value = modes[modes.length - 1]
})

watch(
  [selections, multiplier, fold],
  () => {
    writeStored({
      selections: selections.value,
      multiplier: multiplier.value,
      fold: fold.value,
    })
  },
  { deep: true },
)

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
  const foldOptions = computed(() =>
    availableFoldModes(matchCount.value).map((mode) => ({
      label: foldModeLabel(mode),
      value: mode,
    })),
  )

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
      // 大小 / 双进：同玩法只留新点的一项；胜平负 / 让球可双选
      if (!allowsDualSelect(cell.market)) return false
      return true
    })

    if (allowsDualSelect(cell.market)) {
      const wdlPicks = next.filter(
        (s) => s.fixtureId === fixtureId && s.market === cell.market,
      )
      // 已满双选时再点第三项：清掉本场该玩法，只保留当前点击
      if (wdlPicks.length >= MAX_WDL_PICKS) {
        next = next.filter(
          (s) => !(s.fixtureId === fixtureId && s.market === cell.market),
        )
      }
    }

    next.push({
      fixtureId,
      leagueId: fixture.league_id,
      homeName: fixture.home_team_name || '—',
      awayName: fixture.away_team_name || '—',
      kickoff: `${formatDate(fixture.fixture_date)} ${formatTime(fixture.fixture_date)}`,
      fixtureDate: fixture.fixture_date,
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
    selections,
    groupedSelections,
    isSelected,
    toggleCell,
    clearAll,
    removeFixture,
  }
}
