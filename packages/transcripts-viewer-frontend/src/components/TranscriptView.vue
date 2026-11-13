<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import TranscriptRecord from './TranscriptRecord.vue'
const props = defineProps({ messages: Array, source: String, initialLine: String, lazy: Boolean, uView: Boolean })
const emit = defineEmits(['visible'])
const selectedBlock = ref(null)
const blocks = new Map()
const legend = computed(() => [...new Set(props.messages.map(message=>message.role))])
const options = computed(() => props.messages.map((message, index) => ({
  value: `${index + 1} · ${message.role}`,
  description: message.raw == null ? 'Load original record' : message.raw,
})))
const hiddenTypes=ref(new Set(['session','model_change','thinking_level_change']))
function setTypeVisible(type,visible) {
  if(visible)hiddenTypes.value.delete(type)
  else hiddenTypes.value.add(type)
}
const visibleMessages = computed(() => props.messages.map((message, index) => ({ message, index })).filter(({message})=>!hiddenTypes.value.has(message.role)))
watch(visibleMessages, async (_messages,_,cleanup)=>{
  if(!props.lazy)return
  let disposed=false,observed=[]
  const observer=new IntersectionObserver(entries=>{
    if(disposed)return
    for(const entry of entries)emit('visible',Number(entry.target.dataset.block)-1,entry.isIntersecting)
  })
  cleanup(()=>{disposed=true;observer.disconnect();for(const index of observed)emit('visible',index,false)})
  await nextTick()
  if(!disposed){observed=[...blocks.keys()];for(const element of blocks.values())observer.observe(element)}
},{immediate:true,flush:'post'})
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
    <div class="transcript-controls"><span>{{ messages.length }} messages</span><div class="role-legend" aria-label="Transcript types"><label v-for="role in legend" :key="role"><input type="checkbox" :checked="!hiddenTypes.has(role)" @change="setTypeVisible(role,$event.target.checked)"><i :class="`role-${role}`" aria-hidden="true"></i>{{ role }}</label></div></div>
    <p v-if="!messages.length">Transcript not recorded</p>
    <div class="transcript-layout">
    <nav v-if="messages.length" class="block-navigation" aria-label="Transcript blocks">
      <button v-for="{message,index} in visibleMessages" :key="index" class="block-jump" :class="[{active:selectedBlock===options[index].value}, `role-${message.role}`]" :aria-current="selectedBlock===options[index].value?'true':undefined" :aria-label="`Jump to ${options[index].value}`" :title="options[index].description" @click="jump(options[index].value)"><b>{{ message.line }}</b></button>
    </nav>
    <div class="message-blocks">
    <template v-for="{ message, index } in visibleMessages" :key="index">
      <div :ref="element => { if (element) blocks.set(index, element); else blocks.delete(index) }" :data-block="index + 1" :class="{ 'jump-target': selectedBlock === options[index].value }" tabindex="-1"><div v-if="lazy && message.raw === undefined" class="block-placeholder" :class="`message-${message.role}`"><strong>{{ index + 1 }}</strong><p>Loading block…</p></div><TranscriptRecord v-else :u-view="uView" class="transcript-record" :label="String(message.line)" :message="message" :state-key="`message-${index}`" :class="`message-${message.role}`" /></div>

    </template>
    </div>
    </div>
  </div>
</template>
<style scoped>
.transcript-view { container-type:inline-size; }
.transcript-layout { display:grid;grid-template-columns:minmax(0,1fr);gap:4px;align-items:start; }
.block-navigation { position:sticky;top:0;z-index:1;display:flex;gap:4px;overflow-x:auto;min-width:0;padding:4px 2px;background:white; }
.block-jump { display:flex;align-items:center;gap:4px;flex-shrink:0;border:1px solid #bac9df;border-radius:6px;background:#f6f8fc;color:#254c7f;padding:4px 2px;cursor:pointer;font-size:10px; }
.block-jump b { min-width:20px;text-align:center; }
.block-jump:hover,.block-jump.active { outline:2px solid #4169bb;outline-offset:-2px; }
.role-system { background:#e4e7ec;color:#374151; }
.role-user { background:#dbeafe;color:#1e40af; }
.role-assistant { background:#dcfce7;color:#166534; }
.role-toolResult,.role-tool { background:#fef3c7;color:#854d0e; }
.block-jump span { display:inline;overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }
.message-blocks { min-width:0; }
.block-placeholder,.transcript-record { border-left:3px solid transparent; }
.role-legend { display:flex; justify-content:flex-end; flex-wrap:wrap; gap:4px 8px; }
.role-legend label { cursor:pointer; display:inline-flex; align-items:center; gap:4px; }
.role-legend input { margin:0; }
.role-legend i { display:inline-block; width:8px; height:8px; border-radius:2px; border:1px solid #bac9df; }
.block-placeholder { min-height:120px;box-sizing:border-box;margin-top:4px;padding:8px;background:#f6f8fc;font-size:12px; }

[data-block] { scroll-margin-top: 56px; }
[data-block]:focus, .jump-target { outline: 2px solid #4169bb; outline-offset: 1px; }
.transcript-view { margin-top:4px; }
.transcript-controls { display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:12px;color:#657186; }
.message-system { border-left: 3px solid #a3aec0; }
.message-user { border-left: 3px solid #7096cd; }
.message-assistant { border-left: 3px solid #79a58b; }
.message-toolResult, .message-tool { border-left: 3px solid #c0a46a; }
p { margin: 0; font-size: 12px; color: #657186; }
</style>
