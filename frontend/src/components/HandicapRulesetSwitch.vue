<script setup lang="ts">
import { computed } from 'vue'

import TextSwitch from '@/components/TextSwitch.vue'
import { useHandicapRuleset } from '@/composables/useHandicapRuleset'

const { ruleset, setRuleset } = useHandicapRuleset()

const isJc = computed(() => ruleset.value === 'jc')

function onUpdate(value: boolean) {
  setRuleset(value ? 'jc' : 'asian')
}
</script>

<template>
  <TextSwitch
    :value="isJc"
    checked-text="竞彩"
    unchecked-text="亚盘"
    aria-label="让球玩法"
    @update:value="onUpdate"
  />
</template>
