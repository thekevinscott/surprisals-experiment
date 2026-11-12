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
import {createChartData} from './graphs.js'
const data=reactive({rows:[],warnings:[]})
const loading=ref(false),error=ref('')
const chartData=computed(()=>createChartData(data.rows.filter(row=>row.status)))
import CellChart from './components/CellChart.vue'
import WaitChart from './components/WaitChart.vue'
import SearchSelect from './components/SearchSelect.vue'
import { runRoute, runLink } from './composables/runLinks.js'
import FileViewer from './components/FileViewer.vue'
import Dialog from 'primevue/dialog'
import TranscriptViewer from './components/TranscriptViewer.vue'
import {filePreview,closeFile} from './composables/filePreview.js'
import { fileRoute as parseFileRoute } from './composables/fileMatcher.js'
import ForkDiagram from './components/ForkDiagram.vue'

const route = ref(location.hash)
const syncRoute = () => { route.value = location.hash }
window.addEventListener('hashchange', syncRoute)
onUnmounted(() => window.removeEventListener('hashchange', syncRoute))
const fileRoute = computed(() => parseFileRoute(route.value))
const target = computed(() => runRoute(route.value))
const selected = computed(() => data.rows.find(row => target.value?.id === row.id && row.status))
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
  if(value==='file')refreshController?.abort()
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
  { key: 'exit', label: 'Status / exit' },
  { key: 'cause', label: 'Cause' },
  { key: 'elapsed', label: 'Time' },
  { key: 'turns', label: 'Turns' },
  { key: 'best', label: 'Best advice' },
  { key: 'uCost', label: 'U cost' },
  { key: 'tCost', label: 'T cost' },
  { key: 'modelCost', label: 'Recorded U + T' },
]
const number = value => value == null ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: 1 })
const money = value => value == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)
const time = seconds => seconds == null ? '—' : `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`
</script>

<template>
  <Dialog :visible="!!filePreview" @update:visible="value=>{if(!value)closeFile()}" modal :header="filePreview?.name" class="file-modal" :style="{width:'calc(100vw - 32px)',height:'calc(100dvh - 32px)',maxHeight:'calc(100dvh - 32px)',margin:'16px'}" :draggable="false" :dismissable-mask="false">
    <template #closebutton="{ closeCallback }">
      <a v-for="file in (filePreview?.rawFiles ?? [{url:filePreview?.src,source:filePreview?.name}])" :key="file.url" :href="file.url" target="_blank" rel="noopener" class="modal-action" :aria-label="`Open raw file in new tab: ${file.source}`" :title="`Open raw file: ${file.source}`">↗</a>
      <button type="button" class="modal-action" aria-label="Close" @click="closeCallback">×</button>
    </template>
    <TranscriptViewer v-if="filePreview?.kind==='transcript'" :key="filePreview.url??filePreview.name" v-bind="filePreview" />
    <FileViewer v-else-if="filePreview" :key="filePreview.src" v-bind="filePreview" :show-name="false" />
  </Dialog>
  <main>
    <FileViewer v-if="fileRoute" :src="fileRoute.get('src')" :name="fileRoute.get('name')" :line="fileRoute.get('line')" />
    <template v-else>
    <p v-if="error" role="alert">{{ error }}</p>
    <Tabs v-if="!selected" :value="tab" @update:value="navigateTab" aria-label="Views"><TabList><Tab value="dashboard" as="a" href="#dashboard">Dashboard</Tab><Tab value="graphs" as="a" href="#graphs">Graphs</Tab></TabList></Tabs>
    <section v-if="selected" class="drilldown" aria-label="Run drilldown">
      <a class="back-link" href="#dashboard">← Dashboard</a>
      <div class="drilldown-header">
      <div class="run-summary">
      <dl class="metadata">
        <div><dt>Run</dt><dd>{{ selected.id }}</dd></div>
        <div><dt>Status</dt><dd>{{ selected.status }}<template v-if="selected.exit !== null"> · exit {{ selected.exit }}</template><template v-if="selected.cause"> · {{ selected.cause }}</template></dd></div>
        <div><dt>Duration</dt><dd>{{ time(selected.elapsed) }}</dd></div>
        <div><dt>Windows</dt><dd>{{ number(selected.windows) }}</dd></div>
        <div><dt>Best advice</dt><dd><a v-if="selected.bestTarget" :href="runLink(selected.id, selected.bestTarget)">{{ number(selected.best) }}</a><template v-else>{{ number(selected.best) }}</template> {{ selected.strategy === 'surprisal' ? 'bits' : 'chars' }}</dd></div>
      </dl>
      </div>
      <div class="selectors">
        <SearchSelect label="cap-strategy" :model-value="selected.strategy" :options="strategyOptions" @update:model-value="changeStrategy" />
        <SearchSelect label="Problem" :model-value="selected.problem" :options="problemOptions" @update:model-value="changeProblem" />
      </div>
      </div>
      <div v-if="matchingRuns.length > 1" class="related-runs">Runs for this selection: <a v-for="run in matchingRuns" :key="run.id" :href="'#run/' + encodeURIComponent(run.id)" :aria-current="run.id === selected.id ? 'page' : undefined">{{ run.id }}</a></div>
      <figure class="minimization-loop">
        <ForkDiagram :run="selected" :target="target" />
      </figure>
    </section>
    <section v-else-if="tab === 'graphs'" aria-label="Graphs" class="graphs">
      <p>Graphs from the slides, using live experiment files. ✓ indicates exit 0; ? indicates an open run.</p>
      <template v-if="chartData.series.length">
        <article><h2>Best advice over turns</h2><CellChart :chart-data="chartData" kind="advice" /></article>
        <article><h2>Turns between improvements</h2><CellChart :chart-data="chartData" kind="improvements" /></article>
        <article><h2>Does improvement get harder as advice shrinks?</h2><WaitChart :chart-data="chartData" /></article>
        <p>Passing scores require all configured T samples to pass. Parallel forks share a depth. Hollow markers show turns since the last best at the latest read or exit.</p>
      </template>
      <p v-else-if="!loading">No runs loaded.</p>
    </section>
    <template v-else>
    <p v-for="warning in data.warnings" :key="warning" class="warning">{{ warning }}</p>
    <p v-if="!loading && !error && !data.rows.length" class="empty">No runs loaded. Start <code>transcripts-viewer /path/to/experiment</code> with a directory containing <code>runs/*/run.json</code>.</p>
    <section v-if="!loading && data.rows.length" aria-label="Runs">
      <DataTable :value="data.rows" data-key="id" sort-field="problem" :sort-order="1" :null-sort-order="1" size="small" striped-rows @row-click="openRun($event.data)" class="run-table">
        <ColumnGroup type="header"><Row><Column v-for="column in columns.slice(0,-3)" :key="column.key" :header="column.label" :field="column.key" sortable :rowspan="2" /><Column header="Cost" :colspan="3" /></Row><Row><Column v-for="column in columns.slice(-3)" :key="column.key" :header="column.label" :field="column.key" sortable /></Row></ColumnGroup>
        <Column v-for="column in columns" :key="column.key" :field="column.key" :header="column.label" sortable>
          <template #body="{data:row}">
            <a v-if="column.key === 'problem'" :href="runLink(row.id)" @click.stop>{{ row.problem }}</a>
            <span v-else-if="column.key === 'exit'" class="status" :class="{success:row.exit===0,failed:row.exit!=null&&row.exit!==0}">{{ row.status }}{{ row.exit == null ? '' : ` (${row.exit})` }}</span>
            <span v-else-if="column.key === 'elapsed'">{{ time(row.elapsed) }}</span>
            <span v-else-if="['uCost','tCost','modelCost'].includes(column.key)">{{ money(row[column.key]) }}</span>
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
.modal-action { display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border:0;border-radius:6px;background:transparent;color:inherit;text-decoration:none;font-size:24px;cursor:pointer; }
.modal-action:hover { background:#eef2f7; }
</style>
