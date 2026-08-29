import type { useModal } from 'naive-ui'

type ModalApi = ReturnType<typeof useModal>

/** Shared logout confirm used by the account page login/logout slot. */
export function confirmLogout(
  modal: ModalApi,
  logout: () => Promise<void>,
  onDone?: () => void,
) {
  modal.create({
    preset: 'dialog',
    title: '确认退出登录？',
    autoFocus: false,
    type: 'warning',
    content: '退出后仍可浏览公开内容；收藏与方案会保留在账号下。',
    positiveText: '退出登录',
    negativeText: '取消',
    onPositiveClick: async () => {
      await logout()
      onDone?.()
    },
  })
}
