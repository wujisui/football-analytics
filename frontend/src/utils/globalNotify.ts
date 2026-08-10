import { createDiscreteApi, type ConfigProviderProps } from 'naive-ui'
import { computed } from 'vue'

import { useTheme } from '@/composables/useTheme'

const { naiveTheme, themeOverrides } = useTheme()

const configProviderProps = computed<ConfigProviderProps>(() => ({
  theme: naiveTheme.value,
  themeOverrides: themeOverrides.value,
}))

let api: ReturnType<typeof createDiscreteApi<'notification'>> | null = null

/** Discrete API: long tasks must report their result even after the page that
 * started them is unmounted. */
function getNotification() {
  api ??= createDiscreteApi(['notification'], { configProviderProps })
  return api.notification
}

export function notifySuccess(title: string, content?: string) {
  getNotification().success({ title, content, duration: 4000 })
}

export function notifyError(title: string, content?: string) {
  getNotification().error({ title, content, duration: 8000 })
}
