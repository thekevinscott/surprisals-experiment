<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import TranscriptRecord from './TranscriptRecord.vue'
const props = defineProps({ messages: Array, source: String, initialLine: String })
const selectedBlock = ref(null)
const blocks = new Map()
const roles = { system: 'System prompt', user: 'User', assistant: 'Assistant', toolResult: 'Tool result', tool: 'Tool result' }
const options = computed(() => props.messages.map((message, index) => ({
  value: `${index + 1} · ${roles[message.role] ?? message.role}`,
  description: message.raw == null ? 'Load original record' : message.raw.slice(0, 120),
})))
const visibleMessages = computed(() => props.messages.map((message, index) => ({ message, index })))
async function jump(value) {
  selectedBlock.value = value
  const index = options.value.findIndex(option => option.value === value)
  if (index < 0) return
  await nextTick()
  // Shared row measurements settle after the expanded records are mounted.
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  const block = blocks.get(index)
  block?.focus({ preventScroll: true })
  block?.scrollIntoView({ block: 'start', behavior: 'instant' })
}
watch([()=>props.initialLine,()=>props.messages.length>0],async()=>{
  if(!props.initialLine)return
  const index=props.messages.findIndex(message=>message.line===Number(props.initialLine))
  if(index<0)return
  await nextTick()
  await jump(options.value[index].value)
},{immediate:true})
</script>
<template>
  <div class="transcript-view">
    <div class="transcript-controls"><span>{{ messages.length }} messages</span></div>
    <p v-if="!messages.length">Transcript not recorded</p>
    <div class="transcript-layout">
    <nav v-if="messages.length" class="block-navigation" aria-label="Transcript blocks">
      <button v-for="(option,index) in options" :key="index" class="block-jump" :class="{active:selectedBlock===option.value}" :aria-current="selectedBlock===option.value?'true':undefined" :aria-label="`Jump to ${option.value}`" :title="option.description" @click="jump(option.value)"><b>{{ index+1 }}</b><span>{{ roles[messages[index].role] ?? messages[index].role }}</span></button>
    </nav>
    <div class="message-blocks">
    <template v-for="{ message, index } in visibleMessages" :key="index">
      <div :ref="element => { if (element) blocks.set(index, element); else blocks.delete(index) }" :data-block="index + 1" :class="{ 'jump-target': selectedBlock === options[index].value }" tabindex="-1"><TranscriptRecord :label="`${index + 1} · ${roles[message.role] ?? message.role}`" :message="message" :state-key="`message-${index}`" :class="`message-${message.role}`" /></div>

    </template>
    </div>
    </div>
  </div>
</template>
<style scoped>
.transcript-view { container-type:inline-size; }
.transcript-layout { display:grid;grid-template-columns:32px minmax(0,1fr);gap:6px;align-items:start; }
.block-navigation { position:sticky;top:8px;display:flex;flex-direction:column;gap:3px;max-height:65vh;overflow:auto;min-width:0; }
.block-jump { display:flex;align-items:center;gap:6px;flex-shrink:0;border:1px solid #bac9df;border-radius:4px;background:#f6f8fc;color:#254c7f;padding:5px 3px;cursor:pointer;font-size:10px; }
.block-jump b { min-width:20px;text-align:center; }
.block-jump:hover,.block-jump.active { background:#dfebff;border-color:#4169bb; }
.block-jump span { display:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }
.message-blocks { min-width:0; }
@container(min-width:600px){.transcript-layout{grid-template-columns:155px minmax(0,1fr);}.block-jump span{display:inline;}.block-jump{padding:6px;}}
[data-block] { scroll-margin-top: 8px; }
[data-block]:focus, .jump-target { outline: 2px solid #4169bb; outline-offset: 1px; }
.transcript-view { margin-top:4px; }
.transcript-controls { display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:11px;color:#657186; }
.message-system { border-left: 3px solid #a3aec0; }
.message-user { border-left: 3px solid #7096cd; }
.message-assistant { border-left: 3px solid #79a58b; }
.message-toolResult, .message-tool { border-left: 3px solid #c0a46a; }
p { margin: 0; font-size: 11px; color: #657186; }
</style>
