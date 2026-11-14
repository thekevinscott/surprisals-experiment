<script setup>
import {useContainerScroll,usePageScroll} from './composables/scrollPosition.js'
import {pageReady} from './composables/pageScroll.js'
import {useJsonQuery} from './composables/queryState.js'
import { computed, ref, reactive, watch, nextTick, onUnmounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import ColumnGroup from 'primevue/columngroup'
import Row from 'primevue/row'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import {snapPanelSizes} from './composables/snapPanelSizes.js'
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
const sortField=useJsonQuery('sort','problem'),sortOrder=useJsonQuery('order',1)
const dashboardRows=computed(()=>data.rows.map(row=>({...row,awsCost:awsCost(row,now.value)})))
import ThemeSelect from './components/ThemeSelect.vue'
import RunpodCost from './components/RunpodCost.vue'
import CellChart from './components/CellChart.vue'
import SearchSelect from './components/SearchSelect.vue'
import { runLink } from './composables/runLinks.js'
import FileViewer from './components/FileViewer.vue'
import Dialog from 'primevue/dialog'
import TranscriptViewer from './components/TranscriptViewer.vue'
import {filePreview,closeFile,stepUTurn,restoreModals} from './composables/filePreview.js'
import {connected} from './composables/liveUpdates.js'
import {useRoute,useRouter} from 'vue-router'
import ForkDiagram from './components/ForkDiagram.vue'
import ContentPanel from './components/ContentPanel.vue'
import ProblemFiles from './components/ProblemFiles.vue'
import FilesViewer from './components/FilesViewer.vue'

restoreModals()
usePageScroll()
const modalBody=ref(null)
useContainerScroll('modal',computed(()=>modalBody.value?.parentElement),()=>filePreview.value?.src??filePreview.value?.name)
const showAdviceDiff=useJsonQuery('advice:diff',false)
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
const route=useRoute(),router=useRouter()
const graphPanel=ref(null),transcriptPanel=ref(null),panelSizes=ref([50,50])
function resizePanels({sizes}) {
  panelSizes.value=snapPanelSizes(sizes)
  if(panelSizes.value[0])graphPanel.value.setExpanded(true)
  if(panelSizes.value[1])transcriptPanel.value.setExpanded(true)
}
function collapsePanel(index,expanded) {
  if(!expanded)panelSizes.value=index===0?[0,100]:[100,0]
}
const fileRoute=computed(()=>route.name==='file'?{name:route.params.name,...route.query}:null)
const target=computed(()=>route.meta.run?route.params:null)
const selected = computed(() => data.rows.find(row => target.value?.id === row.id && row.status))
const forkDiagram = ref(null)
const runCharts = computed(() => createRunChartData(selected.value))
const tab = computed(() => route.name === 'graphs' ? 'graphs' : 'dashboard')
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
watch([loading,()=>route.name],async()=>{if(route.name!=='file'&&!loading.value){await nextTick();pageReady.value=true}},{immediate:true,flush:'post'})
const navigateTab = name => router.push({name})
const openRun = row => router.push({name:'run',params:{id:row.id}})
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
  <header class="viewer-toolbar"><ThemeSelect /></header>
  <RunpodCost v-if="route.name === 'dashboard' && !filePreview" :now="now" show-total />
  <Dialog :pt="{transition:{css:false}}" :visible="!!filePreview" @update:visible="value=>{if(!value)closeFile()}" modal :header="filePreview?.title ?? filePreview?.name" class="file-modal" :style="{width:'calc(100vw - 32px)',height:'calc(100dvh - 32px)',maxHeight:'calc(100dvh - 32px)',margin:'16px'}" :draggable="false" :dismissable-mask="false">
    <template v-if="filePreview?.kind==='advice'" #header>
      <div class="advice-modal-heading"><span class="p-dialog-title">{{ filePreview.title }}</span><button type="button" :aria-pressed="showAdviceDiff" :disabled="filePreview.comparisonText==null" :title="filePreview.comparisonText==null?'No previous advice available for this fork':undefined" @click="showAdviceDiff=!showAdviceDiff">Show diff</button></div>
    </template>
    <template #closebutton="{ closeCallback }">
      <a v-for="file in (filePreview?.rawFiles ?? [{url:filePreview?.src,source:filePreview?.name}])" :key="file.url" :href="file.url" target="_blank" rel="noopener" class="modal-action" :aria-label="`Open raw file in new tab: ${file.source}`" :title="`Open raw file: ${file.source}`">↗</a>
      <button type="button" class="modal-action" aria-label="Close" @click="closeCallback">×</button>
    </template>
    <div ref="modalBody">
    <nav v-if="uTurns.length" class="u-turn-navigation" :aria-label="filePreview?.kind==='advice'?'Advice turns':'U turns'">
      <button type="button" :aria-label="filePreview?.kind==='advice'?'Previous advice':'Previous U turn'" title="Previous turn (←)" :disabled="uTurnIndex<=0" @click="stepUTurn(-1)">←</button>
      <button type="button" :aria-label="filePreview?.kind==='advice'?'Next advice':'Next U turn'" title="Next turn (→)" :disabled="uTurnIndex>=uTurns.length-1" @click="stepUTurn(1)">→</button>
    </nav>
    <p v-if="filePreview?.restoreError" role="alert">{{ filePreview.restoreError }}</p>
    <TranscriptViewer v-else-if="filePreview?.kind==='transcript'" :key="filePreview.url??filePreview.name" v-bind="filePreview" />
    <FilesViewer v-else-if="filePreview?.kind==='files'" :key="filePreview.name" :files="filePreview.files" />
    <FileViewer v-else-if="filePreview" :key="filePreview.src" v-bind="filePreview" :show-diff="showAdviceDiff" :show-name="false" />
    </div>
  </Dialog>
  <span v-if="!connected" class="live-dot" role="status" aria-label="Live connection lost; reconnecting" title="Live connection lost; reconnecting"></span>
  <main :class="{'run-page':selected && !fileRoute}">
    <FileViewer v-if="fileRoute" :src="fileRoute.src" :name="fileRoute.name" :line="fileRoute.line" />
    <template v-else>
    <p v-if="error" role="alert">{{ error }}</p>
    <Tabs v-if="!selected" :value="tab" @update:value="navigateTab" aria-label="Views"><TabList><Tab value="dashboard" as="a" :href="router.resolve({name:'dashboard'}).href">Dashboard</Tab><Tab value="graphs" as="a" :href="router.resolve({name:'graphs'}).href">Graphs</Tab></TabList></Tabs>
    <section v-if="selected" class="drilldown" aria-label="Run drilldown">
      <a class="back-link" :href="router.resolve({name:'dashboard'}).href">← Dashboard</a>
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
      <div v-if="matchingRuns.length > 1" class="related-runs">Runs for this selection: <a v-for="run in matchingRuns" :key="run.id" :href="runLink(run.id)" :aria-current="run.id === selected.id ? 'page' : undefined">{{ run.id }}</a></div>
      <Splitter class="run-body" layout="vertical" :gutter-size="8" @resize="resizePanels" @resizeend="resizePanels" :pt="{gutterHandle:{'aria-label':'Resize graph and transcripts'}}">
        <SplitterPanel :size="panelSizes[0]" :min-size="0" :inert="panelSizes[0]===0" :style="{'--panel-share':panelSizes[0]/100}">
        <ContentPanel ref="graphPanel" :expanded="true" @update:expanded="collapsePanel(0,$event)" class="run-section run-graphs" state-key="graphs" scroll-key="graphs" title="Graphs" aria-label="Run graphs">
          <CellChart :key="selected.id" :chart-data="runCharts" clickable @open-turn="forkDiagram.openChartTurn($event)" full-width all-points kind="advice" :controls="false" />
        </ContentPanel>
        </SplitterPanel>
        <SplitterPanel :size="panelSizes[1]" :min-size="0" :inert="panelSizes[1]===0" :style="{'--panel-share':panelSizes[1]/100}">
        <ContentPanel ref="transcriptPanel" :expanded="true" @update:expanded="collapsePanel(1,$event)" class="run-section run-transcripts" state-key="transcripts" scroll-key="transcripts" title="Transcripts" aria-label="Run transcripts">
          <ForkDiagram ref="forkDiagram" :run="selected" :target="target" />
        </ContentPanel>
        </SplitterPanel>
      </Splitter>
    </section>
    <section v-else-if="tab === 'graphs'" aria-label="Graphs"><p>Coming Soon</p></section>
    <template v-else>
    <p v-for="warning in data.warnings" :key="warning" class="warning">{{ warning }}</p>
    <p v-if="!loading && !error && !data.rows.length" class="empty">No runs loaded. Start <code>transcripts-viewer /path/to/experiment</code> with a directory containing <code>runs/*/run.json</code>.</p>
    <section v-if="!loading && data.rows.length" aria-label="Runs">
      <DataTable :value="dashboardRows" data-key="id" :sort-field="sortField" :sort-order="sortOrder" @sort="event=>{sortField=event.sortField;sortOrder=event.sortOrder}" :null-sort-order="1" size="small" striped-rows @row-click="openRun($event.data)" class="run-table">
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
.modal-action:hover { background:var(--viewer-gray); }
</style>
