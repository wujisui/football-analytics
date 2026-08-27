import { readonly, ref } from 'vue'

/** One global tick when local list/recommendation data is rewritten. */
const clientDataEpoch = ref(0)

export function bumpClientDataEpoch(): void {
  clientDataEpoch.value += 1
}

export function useClientDataEpoch() {
  return readonly(clientDataEpoch)
}
