<script setup lang="ts">
withDefaults(
  defineProps<{
    homeName: string
    awayName: string
    /** Prematch / calculator: whole matchup is a text control. */
    clickable?: boolean
    opening?: boolean
    ariaLabel?: string
    /**
     * Equal-width home | mid | away (results with score); home right-aligned,
     * away left-aligned so both names hug the middle score/vs.
     * Default: compact「主 vs 客」group — same as prediction list title.
     */
    spread?: boolean
  }>(),
  {
    clickable: false,
    opening: false,
    ariaLabel: '查看详情',
    spread: false,
  },
)

const emit = defineEmits<{
  click: []
}>()
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
    <n-ellipsis class="team home">{{ homeName }}</n-ellipsis>
    <span class="versus">vs</span>
    <n-ellipsis class="team away">{{ awayName }}</n-ellipsis>
  </button>
  <div v-else class="matchup" :class="{ spread }">
    <n-ellipsis class="team home">{{ homeName }}</n-ellipsis>
    <slot name="middle">
      <span class="versus">vs</span>
    </slot>
    <n-ellipsis class="team away">{{ awayName }}</n-ellipsis>
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

/* n-ellipsis renders its root without our scope id (its own root is the tooltip
 * binder), so every team-name rule has to reach it through :deep. */
.matchup :deep(.team) {
  flex: 0 1 auto;
  min-width: 0;
  max-width: 42%;
  font-size: 13px;
  font-weight: 600;
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

.matchup.spread :deep(.team) {
  max-width: 100%;
}

.matchup.spread :deep(.team.home) {
  justify-self: end;
}

.matchup.spread :deep(.team.away) {
  justify-self: start;
}
</style>
