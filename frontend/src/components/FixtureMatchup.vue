<script setup lang="ts">
import { computed } from 'vue'

import { rankBracket } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    homeName: string
    awayName: string
    /** League table rank when known (detail / list after standings package). */
    homeRank?: number | null
    awayRank?: number | null
    /** Prematch / calculator: whole matchup is a text control. */
    clickable?: boolean
    opening?: boolean
    ariaLabel?: string
    /**
     * 队名被截断时是否自带浮层。外层已经套了 `DetailTabHint` 时必须关掉，
     * 否则同一次 hover 会弹出两个浮层并互相遮挡；全名交给外层那一个显示。
     */
    nameTooltip?: boolean
    /**
     * Equal-width home | mid | away (results with score); home right-aligned,
     * away left-aligned so both names hug the middle score/vs.
     * Default: compact「主 vs 客」group — same as prediction list title.
     */
    spread?: boolean
  }>(),
  {
    homeRank: null,
    awayRank: null,
    clickable: false,
    opening: false,
    ariaLabel: '查看详情',
    nameTooltip: true,
    spread: false,
  },
)

const emit = defineEmits<{
  click: []
}>()

const homeRankText = computed(() => rankBracket(props.homeRank))
const awayRankText = computed(() => rankBracket(props.awayRank))
</script>

<template>
  <!-- Native control: n-button shrinks content and breaks n-ellipsis measure. -->
  <button
    v-if="clickable"
    type="button"
    class="matchup matchup-link"
    :class="{ opening, spread }"
    :aria-label="ariaLabel"
    @click.stop="emit('click')"
  >
    <span class="side home">
      <span v-if="homeRankText" class="rank">{{ homeRankText }}</span>
      <n-ellipsis class="team" :tooltip="nameTooltip">{{ homeName }}</n-ellipsis>
    </span>
    <span class="versus">vs</span>
    <span class="side away">
      <n-ellipsis class="team" :tooltip="nameTooltip">{{ awayName }}</n-ellipsis>
      <span v-if="awayRankText" class="rank">{{ awayRankText }}</span>
    </span>
  </button>
  <div v-else class="matchup" :class="{ spread }">
    <span class="side home">
      <span v-if="homeRankText" class="rank">{{ homeRankText }}</span>
      <n-ellipsis class="team" :tooltip="nameTooltip">{{ homeName }}</n-ellipsis>
    </span>
    <slot name="middle">
      <span class="versus">vs</span>
    </slot>
    <span class="side away">
      <n-ellipsis class="team" :tooltip="nameTooltip">{{ awayName }}</n-ellipsis>
      <span v-if="awayRankText" class="rank">{{ awayRankText }}</span>
    </span>
  </div>
</template>

<style scoped>
.matchup {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  user-select: none;
}

.matchup-link {
  appearance: none;
  margin: 0;
  border: none;
  background: none;
  padding: 0;
  font: inherit;
  color: var(--fa-highlight-text);
  cursor: pointer;
  text-align: inherit;
}

.matchup-link:hover .versus,
.matchup-link:focus-visible .versus,
.matchup-link.opening .versus {
  color: var(--fa-highlight-text);
}

.matchup-link:focus-visible {
  outline: none;
  border-radius: 4px;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--fa-highlight-text) 35%, transparent);
}

/* Rank stays visible; only the name ellipsizes when space is tight. */
.side {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex: 0 1 auto;
  min-width: 0;
  max-width: 42%;
  font-size: 13px;
  font-weight: 600;
}

.rank {
  flex: 0 0 auto;
  font-variant-numeric: tabular-nums;
  opacity: 0.85;
}

/* n-ellipsis root has no parent scope id — reach it through :deep. */
.side :deep(.team) {
  flex: 1 1 auto;
  min-width: 0;
  max-width: 100%;
}

.versus {
  flex-shrink: 0;
  white-space: nowrap;
  color: var(--fa-text-strong);
}

/**
 * Results: equal side columns. Home hugs the score from the left half, away
 * from the right half, so the pair reads as centered on the score.
 */
.matchup.spread {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 8px;
}

.matchup.spread .side {
  max-width: 100%;
  width: 100%;
}

/* Group hugs the score: shrink to content so justify-content can pull it in.
 * (flex:1 here would fill the column and defeat the alignment.) */
.matchup.spread .side :deep(.team) {
  flex: 0 1 auto;
}

.matchup.spread .side.home {
  justify-content: flex-end;
}

.matchup.spread .side.away {
  justify-content: flex-start;
}
</style>
