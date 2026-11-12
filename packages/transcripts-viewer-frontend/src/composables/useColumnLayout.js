import { computed, ref } from 'vue'

export function useColumnLayout(items) {
  const expandedIndex = ref(-1)
  const span = ref(1)
  const hidden = computed(() => items.value.filter((_, index) => index > expandedIndex.value && index < expandedIndex.value + span.value))
  const isVisible = index => !(index > expandedIndex.value && index < expandedIndex.value + span.value)
  const columnSpan = index => index === expandedIndex.value ? span.value : 1
  const columnStyle = index => ({ gridColumn: `${index + 1} / span ${columnSpan(index)}` })
  function resize(index, width) {
    expandedIndex.value = index
    span.value = Math.max(1, Math.min(items.value.length - index, width))
  }
  function reset() { expandedIndex.value = -1; span.value = 1 }
  return { hidden, isVisible, columnSpan, columnStyle, resize, reset }
}
