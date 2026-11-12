import { reactive } from 'vue'

// Paths omit fork IDs so the same turn/section shares disclosure state and tracks.
export function createDisclosureState() {
  const expanded = reactive(new Map())
  const heights = reactive(new Map())
  const sizes = new Map()
  function measure(path, element, height) {
    if (!sizes.has(path)) sizes.set(path, new Map())
    sizes.get(path).set(element, height)
    heights.set(path, Math.max(0, ...sizes.get(path).values()))
  }
  function remove(path, element) {
    const group = sizes.get(path)
    group?.delete(element)
    if (!group?.size) { sizes.delete(path); heights.delete(path) }
    else heights.set(path, Math.max(...group.values()))
  }
  return { expanded, heights, measure, remove }
}
