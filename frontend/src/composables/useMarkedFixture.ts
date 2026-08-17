import { ref } from 'vue'

/** Single reading bookmark across a fixture list (click empty area to toggle). */
export function useMarkedFixture() {
  const markedFixtureId = ref<number | null>(null)

  function isMarked(id: number): boolean {
    return markedFixtureId.value === id
  }

  function toggleMarked(id: number) {
    markedFixtureId.value = markedFixtureId.value === id ? null : id
  }

  function clearMarked() {
    markedFixtureId.value = null
  }

  /** Drop the mark when the fixture leaves the current filtered list. */
  function retainIfPresent(ids: Iterable<number>) {
    const current = markedFixtureId.value
    if (current == null) return
    for (const id of ids) {
      if (id === current) return
    }
    markedFixtureId.value = null
  }

  return {
    markedFixtureId,
    isMarked,
    toggleMarked,
    clearMarked,
    retainIfPresent,
  }
}
