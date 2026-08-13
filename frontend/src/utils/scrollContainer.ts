/** Resolve the actual scrolling element inside a list shell. */
export function findScrollContainer(shell: HTMLElement | null): HTMLElement | null {
  if (!shell) return null
  return (
    // n-virtual-list / vueuc
    (shell.querySelector('.v-vl') as HTMLElement | null) ??
    // Expanded-day fixture table (prefer over the outer day-group shell).
    (shell.querySelector(
      '.day-fixture-table .n-scrollbar-container',
    ) as HTMLElement | null) ??
    // n-data-table body / plain n-scrollbar
    (shell.querySelector('.n-scrollbar-container') as HTMLElement | null) ??
    null
  )
}
