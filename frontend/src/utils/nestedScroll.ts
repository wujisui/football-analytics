/** Keep nested overflow regions scrolling under a parent virtual list / page scroll. */
export function containNestedWheel(e: WheelEvent): void {
  const el = e.currentTarget as HTMLElement | null
  if (!el) return
  if (el.scrollHeight <= el.clientHeight + 1) return

  const max = el.scrollHeight - el.clientHeight
  const delta = e.deltaY
  if ((delta < 0 && el.scrollTop <= 0) || (delta > 0 && el.scrollTop >= max - 0.5)) {
    // At edge: let the outer list continue.
    return
  }

  e.stopPropagation()
  e.preventDefault()
  el.scrollTop += delta
}
