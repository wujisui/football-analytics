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
     * Equal-width home | mid | away (results with score); each name centered
     * in its own half so home and away sit symmetrically around the middle.
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

.team {
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

/* Results: equal columns, each name centered in its own half. */
.matchup.spread {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  justify-items: stretch;
  gap: 8px;
}

.matchup.spread .team {
  flex: unset;
  max-width: 100%;
  width: 100%;
  min-width: 0;
  text-align: center;
}

.matchup.spread .versus {
  justify-self: center;
}
</style>
