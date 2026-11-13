<script setup>
import { computed, ref, reactive, watch, onUnmounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import ColumnGroup from 'primevue/columngroup'
import Row from 'primevue/row'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import {fetchJson,watchData} from './composables/api.js'
import {runStatus} from './composables/runStatus.js'
import {runDuration} from './composables/runDuration.js'
import {awsCost,awsCostTooltip} from './composables/awsCost.js'
import {createRunChartData} from './graphs.js'
const data=reactive({rows:[],warnings:[]})
const loading=ref(false),error=ref('')
const now=ref(Date.now())
const clock=setInterval(()=>{now.value=Date.now()},1000)
onUnmounted(()=>clearInterval(clock))
const dashboardRows=computed(()=>data.rows.map(row=>({...row,awsCost:awsCost(row,now.value)})))
import RunpodCost from './components/RunpodCost.vue'
import CellChart from './components/CellChart.vue'
import SearchSelect from './components/SearchSelect.vue'
import { runRoute, runLink } from './composables/runLinks.js'
import FileViewer from './components/FileViewer.vue'
import Dialog from 'primevue/dialog'
import TranscriptViewer from './components/TranscriptViewer.vue'
import {filePreview,closeFile,stepUTurn} from './composables/filePreview.js'
import {connected} from './composables/liveUpdates.js'
import { fileRoute as parseFileRoute } from './composables/fileMatcher.js'
import ForkDiagram from './components/ForkDiagram.vue'
import ContentPanel from './components/ContentPanel.vue'
import ProblemFiles from './components/ProblemFiles.vue'
import FilesViewer from './components/FilesViewer.vue'

const uTurns=computed(()=>filePreview.value?.uNavigation?.()?.turns ?? [])
const uTurnIndex=computed(()=>uTurns.value.findIndex(turn=>turn.id===filePreview.value?.uTurnId))
function turnKey(event) {
  if(!uTurns.value.length || event.altKey || event.ctrlKey || event.metaKey || event.target?.isContentEditable || event.target?.closest?.('input:not([type=checkbox]):not([type=radio]),textarea,select'))return
  if(event.key==='ArrowLeft' || event.key==='ArrowRight'){
    event.preventDefault()
    stepUTurn(event.key==='ArrowLeft' ? -1 : 1)
  }
}
window.addEventListener('keydown',turnKey)
onUnmounted(()=>window.removeEventListener('keydown',turnKey))
const route = ref(location.hash)
function panelState(name) {
  return computed({
    get:()=>new URLSearchParams(route.value.split('?')[1]).get(name)!=='closed',
    set:open=>{
      const [path,query]=route.value.split('?'),params=new URLSearchParams(query)
      if(open)params.delete(name);else params.set(name,'closed')
      const hash=path+(params.size ? `?${params}` : '')
      history.replaceState(null,'',hash)
      route.value=hash
    },
  })
}
const graphsExpanded=panelState('graphs'),transcriptsExpanded=panelState('transcripts')

const syncRoute = () => { route.value = location.hash }
window.addEventListener('hashchange', syncRoute)
onUnmounted(() => window.removeEventListener('hashchange', syncRoute))
const fileRoute = computed(() => parseFileRoute(route.value))
const target = computed(() => runRoute(route.value))
const selected = computed(() => data.rows.find(row => target.value?.id === row.id && row.status))
const forkDiagram = ref(null)
const runCharts = computed(() => createRunChartData(selected.value))
const tab = computed(() => route.value === '#graphs' ? 'graphs' : 'dashboard')
let refreshController
onUnmounted(()=>refreshController?.abort())
function refresh() {
  refreshController?.abort()
  refreshController=new AbortController()
  const signal=refreshController.signal,id=target.value?.id
  loading.value=true;error.value=''
  const urls=id ? ['/api/runs/index',`/api/runs/${encodeURIComponent(id)}/details`] : ['/api/runs']
  watchData(urls,async signal=>{
    if(!id)return fetchJson(urls[0],signal)
    const [index,summary]=await Promise.all(urls.map(url=>fetchJson(url,signal)))
    return {rows:index.rows.map(row=>row.id===id?summary.row:row),warnings:summary.warnings}
  },{signal,onData:value=>{Object.assign(data,value);loading.value=false;error.value=''},onError:e=>{error.value=e.message;loading.value=false}})
}
watch(()=>fileRoute.value ? 'file' : target.value?.id ?? tab.value, value=>{
  if(value==='file'||value==='graphs'){refreshController?.abort();loading.value=false;error.value=''}
  else refresh()
}, {immediate:true})
const navigateTab = value => { location.hash = value }
const openRun = row => { location.hash = 'run/' + encodeURIComponent(row.id) }
const strategyOptions = computed(() => [...new Set(data.rows.map(r => r.strategy))].map(value => ({ value, description: `${data.rows.filter(r => r.strategy === value).length} runs` })))
const problemOptions = computed(() => [...new Set(data.rows.filter(r => r.strategy === selected.value?.strategy).map(r => r.problem))].map(value => ({ value, description: `${data.rows.filter(r => r.strategy === selected.value?.strategy && r.problem === value).length} runs · ${selected.value?.strategy}` })))
const matchingRuns = computed(() => data.rows.filter(r => r.strategy === selected.value?.strategy && r.problem === selected.value?.problem))
function changeStrategy(value) {
  const options = data.rows.filter(r => r.strategy === value)
  openRun(options.find(r => r.problem === selected.value.problem) ?? options[0])
}
function changeProblem(value) { openRun(data.rows.find(r => r.strategy === selected.value.strategy && r.problem === value)) }


const columns = [
  { key: 'problem', label: 'Problem' },
  { key: 'strategy', label: 'cap-strategy' },
  { key: 'id', label: 'Run' },
  { key: 'status', label: 'Status' },
  { key: 'elapsed', label: 'Time' },
  { key: 'turns', label: 'Turns' },
  { key: 'best', label: 'Best advice' },
  { key: 'uCost', label: 'U cost' },
  { key: 'tCost', label: 'T cost' },
  { key: 'modelCost', label: 'Recorded U + T' },
  { key: 'awsCost', label: 'AWS estimate' },
]
const number = value => value == null ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: 1 })
const money = value => value == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)
const time = seconds => seconds == null ? '—' : `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m ${Math.floor(seconds % 60)}s`
</script>

<template>
  <RunpodCost :now="now" />
  <Dialog :pt="{transition:{css:false}}" :visible="!!filePreview" @update:visible="value=>{if(!value)closeFile()}" modal :header="filePreview?.title ?? filePreview?.name" class="file-modal" :style="{width:'calc(100vw - 32px)',height:'calc(100dvh - 32px)',maxHeight:'calc(100dvh - 32px)',margin:'16px'}" :draggable="false" :dismissable-mask="false">
    <template #closebutton="{ closeCallback }">
      <a v-for="file in (filePreview?.rawFiles ?? [{url:filePreview?.src,source:filePreview?.name}])" :key="file.url" :href="file.url" target="_blank" rel="noopener" class="modal-action" :aria-label="`Open raw file in new tab: ${file.source}`" :title="`Open raw file: ${file.source}`">↗</a>
      <button type="button" class="modal-action" aria-label="Close" @click="closeCallback">×</button>
    </template>
    <nav v-if="uTurns.length" class="u-turn-navigation" aria-label="U turns">
      <button type="button" aria-label="Previous U turn" title="Previous turn (←)" :disabled="uTurnIndex<=0" @click="stepUTurn(-1)">←</button>
      <button type="button" aria-label="Next U turn" title="Next turn (→)" :disabled="uTurnIndex>=uTurns.length-1" @click="stepUTurn(1)">→</button>
    </nav>
    <TranscriptViewer v-if="filePreview?.kind==='transcript'" :key="filePreview.url??filePreview.name" v-bind="filePreview" />
    <FilesViewer v-else-if="filePreview?.kind==='files'" :key="filePreview.name" :files="filePreview.files" />
    <FileViewer v-else-if="filePreview" :key="filePreview.src" v-bind="filePreview" :show-name="false" />
  </Dialog>
  <span v-if="!connected" class="live-dot" role="status" aria-label="Live connection lost; reconnecting" title="Live connection lost; reconnecting"></span>
  <main :class="{'run-page':selected && !fileRoute}">
    <FileViewer v-if="fileRoute" :src="fileRoute.get('src')" :name="fileRoute.get('name')" :line="fileRoute.get('line')" />
    <template v-else>
    <p v-if="error" role="alert">{{ error }}</p>
    <Tabs v-if="!selected" :value="tab" @update:value="navigateTab" aria-label="Views"><TabList><Tab value="dashboard" as="a" href="#dashboard">Dashboard</Tab><Tab value="graphs" as="a" href="#graphs">Graphs</Tab></TabList></Tabs>
    <section v-if="selected" class="drilldown" aria-label="Run drilldown">
      <a class="back-link" href="#dashboard">← Dashboard</a>
      <header class="drilldown-header">
      <div class="run-summary">
      <dl class="metadata">
        <div><dt>Run</dt><dd>{{ selected.id }}</dd></div>
        <div><dt>Status</dt><dd>{{ runStatus(selected) }}</dd></div>
        <div class="duration-metadata"><dt>Duration</dt><dd>{{ time(runDuration(selected,now)) }}</dd></div>
        <div><dt>Windows</dt><dd>{{ number(selected.windows) }}</dd></div>
        <div><dt>Best advice</dt><dd><a v-if="selected.bestTarget" :href="runLink(selected.id, selected.bestTarget)">{{ number(selected.best) }}</a><template v-else>{{ number(selected.best) }}</template> {{ selected.strategy === 'surprisal' ? 'bits' : 'chars' }}</dd></div>
      </dl>
      </div>
      <ProblemFiles :key="selected.id" :run-id="selected.id" />
      <div class="selectors">
        <SearchSelect label="cap-strategy" :searchable="false" :model-value="selected.strategy" :options="strategyOptions" @update:model-value="changeStrategy" />
        <SearchSelect label="Problem" :model-value="selected.problem" :options="problemOptions" @update:model-value="changeProblem" />
      </div>
      </header>
      <div v-if="matchingRuns.length > 1" class="related-runs">Runs for this selection: <a v-for="run in matchingRuns" :key="run.id" :href="'#run/' + encodeURIComponent(run.id)" :aria-current="run.id === selected.id ? 'page' : undefined">{{ run.id }}</a></div>
      <div class="run-body">
        <ContentPanel v-model:expanded="graphsExpanded" class="run-section run-graphs" :class="{collapsed:!graphsExpanded}" title="Graphs" aria-label="Run graphs">
          <CellChart :key="selected.id" :chart-data="runCharts" clickable @open-turn="forkDiagram.openChartTurn($event)" full-width all-points kind="advice" :controls="false" />
        </ContentPanel>
        <ContentPanel v-model:expanded="transcriptsExpanded" class="run-section run-transcripts" :class="{collapsed:!transcriptsExpanded}" title="Transcripts" aria-label="Run transcripts">
          <ForkDiagram ref="forkDiagram" :run="selected" :target="target" />
        </ContentPanel>
      </div>
    </section>
    <section v-else-if="tab === 'graphs'" aria-label="Graphs"><p>Coming Soon</p></section>
    <template v-else>
    <p v-for="warning in data.warnings" :key="warning" class="warning">{{ warning }}</p>
    <p v-if="!loading && !error && !data.rows.length" class="empty">No runs loaded. Start <code>transcripts-viewer /path/to/experiment</code> with a directory containing <code>runs/*/run.json</code>.</p>
    <section v-if="!loading && data.rows.length" aria-label="Runs">
      <DataTable :value="dashboardRows" data-key="id" sort-field="problem" :sort-order="1" :null-sort-order="1" size="small" striped-rows @row-click="openRun($event.data)" class="run-table">
        <ColumnGroup type="header"><Row><Column v-for="column in columns.slice(0,-4)" :key="column.key" :header="column.label" :field="column.key" sortable :rowspan="2" /><Column header="Cost" :colspan="4" /></Row><Row><Column v-for="column in columns.slice(-4)" :key="column.key" :field="column.key" sortable><template #header><span :title="column.key==='awsCost' ? awsCostTooltip : undefined">{{ column.label }}</span></template></Column></Row></ColumnGroup>
        <Column v-for="column in columns" :key="column.key" :field="column.key" :header="column.label" sortable>
          <template #body="{data:row}">
            <a v-if="column.key === 'problem'" :href="runLink(row.id)" @click.stop>{{ row.problem }}</a>
            <span v-else-if="column.key === 'status'" class="status" :class="{success:row.exit===0,failed:row.exit!=null&&row.exit!==0}">{{ runStatus(row) }}</span>
            <span v-else-if="column.key === 'elapsed'">{{ time(runDuration(row,now)) }}</span>
            <span :title="column.key==='awsCost' ? awsCostTooltip : undefined" v-else-if="['uCost','tCost','modelCost','awsCost'].includes(column.key)">{{ money(row[column.key]) }}</span>
            <a v-else-if="column.key === 'best' && row.bestTarget" :href="runLink(row.id,row.bestTarget)" @click.stop>{{ number(row.best) }} {{ row.strategy==='surprisal'?'bits':'chars' }}</a>
            <span v-else-if="column.key === 'best'">{{ number(row.best) }}</span>
            <span v-else>{{ row[column.key] ?? '—' }}</span>
          </template>
        </Column>
      </DataTable>
    </section>
    </template>
    </template>
  </main>
</template>

<style>
.live-dot { position:fixed; top:10px; right:10px; z-index:1000; width:10px; height:10px; border-radius:50%; background:#e6b800; animation:live-pulse 1.2s ease-in-out infinite; }
@keyframes live-pulse { 50% { opacity:.3; transform:scale(.8); } }
.modal-action { display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border:0;border-radius:6px;background:transparent;color:inherit;text-decoration:none;font-size:12px;cursor:pointer; }
.modal-action:hover { background:#eef2f7; }
</style>
