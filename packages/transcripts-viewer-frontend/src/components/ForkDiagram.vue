<script setup>
import {runStatus} from '../composables/runStatus.js'
import { ref, watch, provide, nextTick } from 'vue'
import { fetchJson,watchData } from '../composables/api.js'
import { runLink } from '../composables/runLinks.js'
import { createDisclosureState } from '../composables/disclosureState.js'
import ProblemFiles from './ProblemFiles.vue'
import ForkWindow from './ForkWindow.vue'
const props = defineProps({ run: Object, target: Object })
const windows = ref([])
const windowViews = ref([])
const apiUrl = path => `/api/runs/${encodeURIComponent(props.run.id)}/${path.split('/').map(encodeURIComponent).join('/')}`
provide('apiUrl',apiUrl)
const rawUrl = path => !path || path.includes(', ') ? undefined : apiUrl(path.startsWith('problem/') ? path : `files/${path}`)
provide('rawSourceUrl', rawUrl)
provide('sourceUrl', (path, line) => {
  const source = rawUrl(path)
  if (!source) return source
  const viewer = new URL(location.href)
  viewer.hash = `files/${encodeURIComponent(path)}?${new URLSearchParams({src:source,...(line ? {line:String(line)} : {})})}`
  return viewer.href
})
const loading = ref(false)
provide('disclosureState', createDisclosureState())
provide('disclosurePath', () => props.run.id)
provide('runLink', source => runLink(props.run.id, source))
const error = ref('')
watch(() => props.run.id, async (_, __, onCleanup) => {
  const controller = new AbortController()
  onCleanup(() => controller.abort())
  windows.value = []
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
    <ProblemFiles :key="run.id" />
    <ForkWindow ref="windowViews" v-for="(window, index) in windows" :key="window.id" :window="window" :target="target" :has-next="index < windows.length - 1" />
    <p v-if="loading">Loading run details…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <p v-else-if="!windows.length">No windows recorded. Run status: {{ runStatus(run) }}</p>
    <div v-else class="run-end">{{ runStatus(run) }}</div>
  </div>
</template>
<style scoped>
.fork-diagram { overflow-x: auto; }
.run-end { padding: 16px; margin-top: 20px; text-align: center; background: #edf1f7; border-radius: 6px; font-size: 12px; }
</style>
