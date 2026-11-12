<script setup>
import { ref } from 'vue'
const props = defineProps({ span: Number, max: Number, label: String })
const emit = defineEmits(['resize'])
const dragging = ref(false)
let origin = 0, initialSpan = 1, step = 1
function start(event) {
  const grid = event.currentTarget.closest('.phase')
  const count = Number(getComputedStyle(grid).getPropertyValue('--fork-count'))
  const gap = parseFloat(getComputedStyle(grid).columnGap)
  step = (grid.clientWidth + gap) / count
  origin = event.clientX
  initialSpan = props.span
  dragging.value = true
  event.currentTarget.setPointerCapture(event.pointerId)
}
function move(event) {
  if (dragging.value) emit('resize', Math.max(1, Math.min(props.max, initialSpan + Math.round((event.clientX - origin) / step))))
}
</script>
<template>
  <div class="column-resize" :class="{ dragging }" role="separator" aria-orientation="vertical" :aria-label="`Resize ${label}`"
    :aria-valuenow="span" :aria-valuemin="1" :aria-valuemax="max" :aria-valuetext="`${span} columns wide`" tabindex="0"
    title="Drag to resize. Arrow keys resize; Home resets."
    @pointerdown.prevent="start" @pointermove="move" @pointerup="dragging = false" @pointercancel="dragging = false"
    @keydown.right.prevent="emit('resize', Math.min(max, span + 1))" @keydown.left.prevent="emit('resize', Math.max(1, span - 1))"
    @keydown.home.prevent="emit('resize', 1)"><span>⋮</span></div>
</template>
<style scoped>
.column-resize { position: absolute; top: 0; bottom: 0; right: -9px; width: 16px; z-index: 2; cursor: ew-resize; touch-action: none; display: flex; align-items: flex-start; justify-content: center; border-radius: 6px; }
span { margin-top: 12px; background: #fff; border: 1px solid #aebed4; border-radius: 4px; color: #4169bb; font-size: 16px; line-height: 24px; width: 12px; text-align: center; }
.column-resize:hover, .dragging, .column-resize:focus-visible { background: #4169bb20; outline: 2px solid #4169bb; }
</style>
