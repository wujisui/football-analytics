import { computed, ref, watch } from 'vue'

import {
  DEFAULT_HANDICAP_RULESET,
  HANDICAP_RULESET_STORAGE_KEY,
  parseHandicapRuleset,
  type HandicapRuleset,
} from '@/utils/handicapRuleset'

const STORAGE_KEY = HANDICAP_RULESET_STORAGE_KEY

function readStored(): HandicapRuleset {
  try {
    return parseHandicapRuleset(localStorage.getItem(STORAGE_KEY))
  } catch {
    return DEFAULT_HANDICAP_RULESET
  }
}

const ruleset = ref<HandicapRuleset>(readStored())

watch(ruleset, (value) => {
  try {
    localStorage.setItem(STORAGE_KEY, value)
  } catch {
    /* ignore */
  }
})

export function useHandicapRuleset() {
  const isAsian = computed(() => ruleset.value === 'asian')

  function setRuleset(value: HandicapRuleset) {
    ruleset.value = parseHandicapRuleset(value)
  }

  return {
    ruleset,
    isAsian,
    setRuleset,
  }
}
