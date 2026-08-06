/** Capture a DOM node as PNG; prefer OS share sheet (album) over file download. */

export type SaveDomAsPngResult =
  | { mode: 'shared' }
  | { mode: 'downloaded' }
  /** iOS: `<a download>` goes to Files, not Photos — show image for share / long-press. */
  | { mode: 'preview'; url: string; file: File }

function isAppleTouchDevice(): boolean {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent
  if (/iPad|iPhone|iPod/.test(ua)) return true
  // iPadOS may report as Mac
  return navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1
}

export async function sharePngFile(file: File): Promise<boolean> {
  const data: ShareData = { files: [file], title: file.name }
  if (typeof navigator.canShare !== 'function' || !navigator.canShare(data)) {
    return false
  }
  try {
    await navigator.share(data)
    return true
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') throw err
    return false
  }
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  try {
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.rel = 'noopener'
    document.body.appendChild(link)
    link.click()
    link.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
}

export async function saveDomAsPng(
  el: HTMLElement,
  filename: string,
): Promise<SaveDomAsPngResult> {
  const { toBlob } = await import('html-to-image')
  const bg =
    getComputedStyle(document.documentElement)
      .getPropertyValue('--fa-bg-elevated')
      .trim() || '#ffffff'
  const blob = await toBlob(el, {
    pixelRatio: Math.min(2, window.devicePixelRatio || 2),
    cacheBust: true,
    backgroundColor: bg,
    filter: (node) => {
      if (!(node instanceof HTMLElement)) return true
      return !node.hasAttribute('data-export-hide')
    },
  })
  if (!blob) throw new Error('生成图片失败')

  const file = new File([blob], filename, { type: 'image/png' })

  // iOS/iPadOS: awaited capture consumes user activation, so share here usually fails
  // and `<a download>` only lands in「文件」. Hand back a preview for a fresh share tap
  // (or long-press → 存储到照片).
  if (isAppleTouchDevice()) {
    return { mode: 'preview', url: URL.createObjectURL(blob), file }
  }

  if (await sharePngFile(file)) return { mode: 'shared' }

  triggerDownload(blob, filename)
  return { mode: 'downloaded' }
}
