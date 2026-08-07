/** Resolve the actual scrolling element inside a list shell. */
export function findScrollContainer(shell: HTMLElement | null): HTMLElement | null {
  if (!shell) return null
  return (
    // n-virtual-list / vueuc
    (shell.querySelector('.v-vl') as HTMLElement | null) ??
    // FixtureList day sections (native sticky scroll)
    (shell.querySelector('.fixture-list-scroll') as HTMLElement | null) ??
    // plain n-scrollbar
    (shell.querySelector('.n-scrollbar-container') as HTMLElement | null) ??
    null
  )
}
