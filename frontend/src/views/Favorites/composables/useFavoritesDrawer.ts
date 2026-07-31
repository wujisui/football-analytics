import { ref } from 'vue'

const show = ref(false)

export function useFavoritesDrawer() {
  function open() {
    show.value = true
  }

  function close() {
    show.value = false
  }

  function toggle() {
    show.value = !show.value
  }

  return { show, open, close, toggle }
}
