<script setup>
import { computed } from 'vue'
import {highlightParts} from '../composables/adviceDiff.js'
import Tooltip from 'primevue/tooltip'
const vTooltip = Tooltip
const props = defineProps({ text: String, tokens: Array, additions:{type:Array,default:()=>[]} })
const parts = computed(() => {
  const text = props.text ?? ''
  // Preserve the advice exactly if a scorer's token strings don't reconstruct it.
  if (!props.tokens?.length || props.tokens.map(t => t[0]).join('') !== text) {
    return [{ text, bits: null }]
  }
  return props.tokens.map(([text, bits]) => ({text, bits}))
})
const highlighted=computed(()=>{
  let offset=0
  return parts.value.map(part=>{const pieces=highlightParts(part.text,props.additions,offset);offset+=part.text.length;return {...part,pieces}})
})
const color = bits => {
  const t = Math.min(1, Math.max(0, bits / 20))
  return `color-mix(in srgb, var(--viewer-token-high) ${t * 100}%, var(--viewer-token-low))`
}
</script>
<template><template v-for="(part, index) in highlighted" :key="index"><span :class="{'scored-token':part.bits!==null}" :style="part.bits!==null ? {backgroundColor:color(part.bits)} : undefined" v-tooltip.top="part.bits!==null ? `${Number(part.bits.toFixed(3))} bits` : null" :aria-label="part.bits!==null ? `${Number(part.bits.toFixed(3))} bits` : undefined"><span v-for="(piece,i) in part.pieces" :key="i" :class="{'advice-added':piece.added}">{{ piece.text }}</span></span></template></template>
<style scoped>
.advice-added { background-color:var(--viewer-added);animation:advice-fade 3s ease 1s forwards;box-decoration-break:clone;-webkit-box-decoration-break:clone; }
@keyframes advice-fade { to { background-color:transparent; } }
.scored-token { border-radius: 2px; box-decoration-break: clone; -webkit-box-decoration-break: clone; }
</style>
