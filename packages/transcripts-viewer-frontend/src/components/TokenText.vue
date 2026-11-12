<script setup>
import { computed } from 'vue'
const props = defineProps({ text: String, tokens: Array, start: { type: Number, default: 0 }, end: Number })
const parts = computed(() => {
  const text = props.text ?? ''
  const end = props.end ?? Array.from(text).length
  // Preserve the advice exactly if a scorer's token strings don't reconstruct it.
  if (!props.tokens?.length || props.tokens.map(t => t[0]).join('') !== text) {
    return [{ text: Array.from(text).slice(props.start, end).join(''), bits: null }]
  }
  let offset = 0
  return props.tokens.flatMap(([token, bits]) => {
    const chars = Array.from(token), from = Math.max(0, props.start - offset), to = Math.min(chars.length, end - offset)
    offset += chars.length
    return to > from ? [{ text: chars.slice(from, to).join(''), token, bits }] : []
  })
})
const color = bits => {
  const t = Math.min(1, Math.max(0, bits / 20))
  return `rgb(${Math.round(255 - 31 * t)} ${Math.round(252 - 92 * t)} ${Math.round(230 - 230 * t)})`
}
</script>
<template><template v-for="(part, index) in parts" :key="index"><span v-if="part.bits !== null" class="scored-token" :style="{ backgroundColor: color(part.bits) }" :title="`${JSON.stringify(part.token)}: ${part.bits} bits`">{{ part.text }}</span><template v-else>{{ part.text }}</template></template></template>
<style scoped>
.scored-token { border-radius: 2px; box-decoration-break: clone; -webkit-box-decoration-break: clone; }
</style>
