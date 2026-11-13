<script setup>
import {createForkPhaseChartData} from '../graphs.js'
import {openTranscript} from '../composables/filePreview.js'
import {runStatus} from '../composables/runStatus.js'
import { ref, watch, provide, nextTick } from 'vue'
import { fetchJson,watchData } from '../composables/api.js'
import { runLink } from '../composables/runLinks.js'
import { createDisclosureState } from '../composables/disclosureState.js'
import ForkWindow from './ForkWindow.vue'
const props = defineProps({ run: Object, target: Object })
const windows = ref([])
const forkRange = ref(null)
provide('forkRange',forkRange)
const windowViews = ref([])
const apiUrl = path => `/api/runs/${encodeURIComponent(props.run.id)}/${path.split('/').map(encodeURIComponent).join('/')}`
provide('apiUrl',apiUrl)
function uTurnContext(source) {
  for(const window of windows.value)for(const fork of window.forks){
    const turns=[...fork.parallel,...fork.solo].sort((a,b)=>a.id-b.id)
    const turn=turns.find(turn=>turn.source===source)
    if(turn)return {window:window.id,fork:fork.id,turn:turn.id,turns:turns.map(({id,metadata})=>({id,metadata}))}
  }
}
provide('uTurnContext',uTurnContext)
provide('sampleCount', () => props.run.samples)
provide('forkChart', (window,id,solo) => createForkPhaseChartData(props.run,window,id,solo))
const rawUrl = path => !path || path.includes(', ') ? undefined : apiUrl(path.startsWith('problem/') ? path : `files/${path}`)
provide('rawSourceUrl', rawUrl)
const sourceUrl = (path, line) => {
  const source = rawUrl(path)
  if (!source) return source
  const viewer = new URL(location.href)
  viewer.hash = `files/${encodeURIComponent(path)}?${new URLSearchParams({src:source,...(line ? {line:String(line)} : {})})}`
  return viewer.href
}
provide('sourceUrl',sourceUrl)
async function openChartTurn({window,fork,turn}) {
  const runId=props.run.id
  if(loading.value) {
    const data=await fetchJson(`/api/runs/${encodeURIComponent(runId)}`)
    if(props.run.id!==runId)return
    windows.value=data.diagram
  }
  const source=`windows/${window}/forks/${fork}/turns/${turn}`
  if(!uTurnContext(source))return
  const transcript=`windows/${window}/forks/${fork}/u/transcript.jsonl`
  openTranscript({name:'U transcript',uView:true,sourceUrl,files:[{source:transcript,url:rawUrl(transcript)}],uNavigation:()=>uTurnContext(source)})
}
provide('openChartTurn',openChartTurn)
defineExpose({openChartTurn})
const loading = ref(false)
provide('disclosureState', createDisclosureState())
provide('disclosurePath', () => props.run.id)
provide('runLink', source => runLink(props.run.id, source))
const error = ref('')
watch(() => props.run.id, async (_, __, onCleanup) => {
  const controller = new AbortController()
  onCleanup(() => controller.abort())
  windows.value = []
  forkRange.value = null
  loading.value = true
  error.value = ''
  const url=`/api/runs/${encodeURIComponent(props.run.id)}`
  watchData([url],signal=>fetchJson(url,signal),{
    signal:controller.signal,
    onData:data=>{windows.value=data.diagram;loading.value=false;error.value=''},
    onError:e=>{error.value=e.message;loading.value=false},
  })
}, { immediate: true })
watch([() => windows.value.length > 0, () => props.target], async () => {
  if (props.target?.window == null) return
  await nextTick()
  await Promise.all(windowViews.value.map(view => view.reveal(props.target)))
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  const t = props.target
  const selector = `[data-window="${t.window}"]` + (t.fork == null ? '' : ` [data-fork="${t.fork}"]`) + (t.turn == null ? '' : ` [data-turn="${t.turn}"]`)
  document.querySelector(selector)?.scrollIntoView({block:'start'})
}, { deep:true })
</script>
<template>
  <div class="fork-diagram" aria-label="Recorded run windows and U turns">
    <ForkWindow ref="windowViews" v-for="(window, index) in windows" :key="window.id" :window="window" :target="target" :has-next="index < windows.length - 1" />
    <p v-if="loading">Loading run details…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <p v-else-if="!windows.length">No windows recorded. Run status: {{ runStatus(run) }}</p>
  </div>
</template>
<style scoped>
.fork-diagram { overflow-x: auto; }
</style>
