<script setup>
import { computed, ref, useId, onMounted, onUnmounted } from 'vue'

const props = defineProps({ chartData:Object, allPoints:Boolean, fullWidth:Boolean, plotWidth:{type:Number,default:840}, kind: { type: String, required: true }, controls:{type:Boolean,default:true} })
const armSel = ref(props.chartData.arms[0])
const selectedArm = computed(() => props.controls ? armSel.value : props.chartData.arms[0])
const unit = computed(() => selectedArm.value === 'surprisal' ? 'bits' : 'characters')
const mode = ref('all')
const data = computed(()=>props.chartData.series)
const domains = computed(()=>props.chartData.domains)
const range = defineModel('range', {default:null})
const knob = ref(null)
const clipId = useId()
const dots = ref(true)
const highlightedSeries = ref(null)
const logarithmic = ref(false)
const exitOf = s => s.exit_code ?? undefined
const statusMark = s => s.running ? '?' : exitOf(s) === 0 ? '✓' : '✕'
const endPoint = s => props.kind === 'advice' ? points(s).at(-1) : s.streak[0]

const svgElement = ref(null)
const measuredWidth = ref(null)
let resizeObserver
onMounted(() => {
  if (!props.fullWidth) return
  resizeObserver = new ResizeObserver(([entry]) => {
    const {width, height} = entry.contentRect
    if (width > 0 && height > 0) measuredWidth.value = width / height * 285 - 120
  })
  resizeObserver.observe(svgElement.value)
})
onUnmounted(() => resizeObserver?.disconnect())
const width = computed(() => measuredWidth.value ?? props.plotWidth)
const selected = computed(() => data.value.filter(s => s.strategy === selectedArm.value))
const modes = computed(() => ['all', ...new Set(selected.value.map(s => s.problem))])
const visible = computed(() => selected.value.filter(s => mode.value === 'all' || s.problem === mode.value))
const legendWindows = computed(() => {
  const windows = new Map()
  for (const series of visible.value) {
    if (!windows.has(series.window)) windows.set(series.window,[])
    windows.get(series.window).push(series)
  }
  return [...windows].sort((a,b)=>a[0]-b[0])
})
const chartKey = computed(() => props.kind === 'advice' && unit.value === 'bits' ? 'surprisal' : props.kind)
const points = s => props.allPoints && props.kind === 'advice' ? (s.scored.length && s.startPoint ? [s.startPoint,...s.scored] : s.scored) : s[props.kind]
const domain = computed(() => domains.value[chartKey.value] || { x: [0, 250], y: [0, 54] })
const yrange = computed(() => range.value || domain.value.y)
const ymin = computed(() => yrange.value[0])
const ymax = computed(() => yrange.value[1])
const yticks = computed(() => {
  if (logarithmic.value) return [0,1,2,5,10,20,50,100,200,500,1000,2000,5000,10000,20000,50000,100000].filter(v=>v>=ymin.value&&v<=ymax.value)
  const target = (ymax.value - ymin.value) / 8
  const magnitude = 10 ** Math.floor(Math.log10(target))
  const step = [1, 2, 5, 10].find(n => n * magnitude >= target) * magnitude
  const first = Math.ceil(ymin.value / step) * step
  return Array.from({length: Math.floor((ymax.value - first) / step) + 1}, (_, i) => first + i * step)
})
const xticks = computed(() => {
  const [start,end]=domain.value.x, step=end-start<=20 ? 2 : 10
  const first=Math.ceil(start/step)*step
  return Array.from({length:Math.floor((end-first)/step)+1},(_,i)=>first+i*step)
})
const x = v => (v-domain.value.x[0]) / (domain.value.x[1]-domain.value.x[0]) * width.value
const scale = v => logarithmic.value ? Math.log1p(v) : v
const y = v => 240 - (scale(v) - scale(ymin.value)) / (scale(ymax.value) - scale(ymin.value)) * 210
const [d0, d1] = [() => domain.value.y[0], () => domain.value.y[1]]
const sliderY = v => 240 - (v - d0()) / (d1() - d0()) * 210
const sliderValue = py => d0() + (240 - py) / 210 * (d1() - d0())
function grab(which, event) {
  event.currentTarget.setPointerCapture(event.pointerId)
  knob.value = which
}
function slide(event) {
  if (!knob.value) return
  const py = new DOMPoint(event.clientX, event.clientY).matrixTransform(event.currentTarget.ownerSVGElement.getScreenCTM().inverse()).y
  const v = Math.max(d0(), Math.min(d1(), sliderValue(py)))
  const gap = (d1() - d0()) / 50
  const [lo, hi] = yrange.value
  range.value = knob.value === 'lo' ? [Math.min(v, hi - gap), hi] : [lo, Math.max(v, lo + gap)]
}
function path(s) {
  if (props.kind === 'improvements') {
    const imp = s.improvements
    if (!imp.length) return ''
    return `M${x(imp[0][0] - imp[0][1])},${y(0)}` + imp.map(([b, g]) => ` L${x(b)},${y(g)} L${x(b)},${y(0)}`).join('')
  }
  return points(s).map((p, i) => `${i ? (props.kind === 'advice' && !props.allPoints ? 'H' + x(p[0]) + 'V' : 'L' + x(p[0]) + ',') : 'M' + x(p[0]) + ','}${y(p[1])}`).join(' ')
}
</script>

<template>
  <div class="cell-chart" :class="{'full-width':fullWidth}" :data-kind="kind" @pointerdown.stop @pointermove.stop @pointerup.stop @pointercancel.stop @click.stop @dblclick.stop>
    <div class="filters" @click.stop @keydown.stop>
      <template v-if="controls && chartData.arms.length > 1">
      <span>Strategy</span>
      <button v-for="value in chartData.arms" :key="value" :aria-pressed="armSel === value" @click="armSel = value; mode = 'all'; range = null">{{ value }}</button>
      </template>
      <template v-if="controls && modes.length > 2">
      <span style="margin-left:12px">Problem</span>
      <button v-for="value in modes" :key="value" :aria-pressed="mode === value" :data-mode="value" @click="mode = value">{{ value }}</button>
      </template>
      <button v-if="kind === 'advice'" :aria-pressed="logarithmic" @click="logarithmic = !logarithmic">Log (1 + score)</button>
      <button v-if="controls && kind === 'advice'" class="dots" :aria-pressed="dots" @click="dots = !dots">all passing turns</button>
    </div>
    <svg ref="svgElement" :viewBox="`0 0 ${width + 120} 285`" role="img" :aria-label="`${kind} by ${controls ? 'cell' : 'fork'}`">
      <defs>
        <clipPath :id="clipId"><rect x="-6" y="24" :width="width + 12" height="222" /></clipPath>
      </defs>
      <g class="y-slider">
        <line x1="10" x2="10" y1="30" y2="240" class="track" />
        <line x1="10" x2="10" :y1="sliderY(ymax)" :y2="sliderY(ymin)" class="selected" />
        <circle v-for="which in ['lo', 'hi']" :key="which" cx="10" :cy="sliderY(which === 'lo' ? ymin : ymax)" r="6" class="knob"
          :data-knob="which" @pointerdown.stop.prevent="grab(which, $event)" @pointermove.stop="slide"
          @pointerup.stop="knob = null" @pointercancel.stop="knob = null" />
      </g>
      <text x="32" y="135" transform="rotate(-90 32 135)" text-anchor="middle" class="axis-title">{{ kind === 'advice' ? (unit === 'bits' ? 'Advice (bits)' : 'Advice (characters)') : 'Turns between improvements' }}</text>
      <g transform="translate(95,0)" data-plot="shared">
        <g v-for="tick in yticks" :key="tick">
          <line x1="0" :x2="width" :y1="y(tick)" :y2="y(tick)" stroke="#e4e3de" />
          <text x="-8" :y="y(tick) + 3" text-anchor="end">{{ tick.toLocaleString() }}</text>
        </g>
        <g v-for="tick in xticks" :key="tick">
          <text :x="x(tick)" y="255" text-anchor="middle">{{ tick }}</text>
        </g>
        <g v-for="window in chartData.windowPositions" :key="`window-${window.id}`" class="window-boundary" :data-window="window.id">
          <line :x1="x(window.depth)" :x2="x(window.depth)" y1="25" y2="240" vector-effect="non-scaling-stroke" />
          <text :x="x(window.depth) + 4" y="18">Window {{ window.id }}</text>
        </g>
        <text :x="width / 2" y="271" text-anchor="middle" class="axis-title">Turn (sequential depth)</text>
        <line v-if="kind === 'improvements' && ymin <= 50 && ymax >= 50" x1="0" :x2="width" :y1="y(50)" :y2="y(50)" stroke="#777" stroke-dasharray="2 3" />
        <g :clip-path="`url(#${clipId})`">
        <g v-for="s in visible" :key="s.cell" :data-cell="s.cell" :data-mode="s.problem" :class="{'series-dimmed':highlightedSeries!==null && highlightedSeries!==s.cell,'series-highlighted':highlightedSeries===s.cell}">
          <path :d="path(s)" fill="none" :stroke="s.color" stroke-width="0.5" />
          <circle v-for="(p, i) in (!dots ? [] : kind === 'advice' ? (allPoints ? s.scored : s.passing) : s.improvements).filter(p => p[1] >= ymin && p[1] <= ymax)" :key="`point-${i}`" :cx="x(p[0])" :cy="y(p[1])" :r="allPoints ? 2.5 : kind === 'advice' ? 1.4 : 2" :fill="allPoints && !p[2] ? 'white' : s.color" :stroke="allPoints ? s.color : undefined" :data-passed="allPoints ? p[2] : undefined" :opacity="allPoints ? 1 : kind === 'advice' ? .25 : 1" />
          <g v-for="(p,i) in (kind === 'improvements' ? s.streak : [])" :key="`streak-${i}`">
            <line :x1="x(p[0] - p[1])" :y1="y(0)" :x2="x(p[0])" :y2="y(p[1])"
              :stroke="s.color" :stroke-width="p[1] >= 50 ? 1 : 0.5" class="stop-rule-line" />
            <circle :cx="x(p[0])" :cy="y(p[1])" :r="p[1] >= 50 ? 3 : 1.5"
              :fill="p[1] >= 50 ? s.color : 'white'" :stroke="s.color" />
          </g>
        </g>
        </g>

      </g>
    </svg>
    <p v-if="allPoints" class="outcome-legend">● T passed · ○ T failed / incomplete</p>
    <div v-if="allPoints" class="window-chart-legend" aria-label="Window and fork legend">
      <section v-for="[window,series] in legendWindows" :key="window" class="legend-window">
        <strong>Window {{ window }}</strong>
        <div v-for="s in series" :key="s.cell" class="legend-fork" :class="{continues:s.continues}" :title="s.continues ? 'Continues into solo phase' : undefined" tabindex="0" @mouseenter="highlightedSeries=s.cell" @mouseleave="highlightedSeries=null" @focus="highlightedSeries=s.cell" @blur="highlightedSeries=null" :style="{borderColor:s.continues ? '#15803d' : s.color}"><span :style="{background:s.color}"></span>Fork {{ s.fork }}<b v-if="s.continues" class="continuation-label">Continues</b><small v-if="s.scored.length">{{ s.scored.at(-1)[1].toLocaleString(undefined,{maximumFractionDigits:3}) }}</small></div>
      </section>
    </div>
    <ul v-else class="chart-legend">
      <li v-for="s in visible" :key="s.cell"><span :style="{background:s.color}"></span>{{ s.label ?? `${s.problem} ${s.cell.split('-').slice(2).join('-')}` }}{{ kind === 'advice' ? (points(s).length ? ` · ${endPoint(s)[1].toLocaleString(undefined,{maximumFractionDigits:1})}` : (allPoints ? ' · no scored advice' : ' · no all-samples pass')) : '' }} {{ statusMark(s) }}</li>
    </ul>
  </div>
</template>

<style scoped>
.cell-chart { position:relative; width: 100%; margin: 4px 0; }
.filters { display:flex; align-items:center; gap:5px; font-size:11px; min-height:30px; flex-wrap:wrap; }
button { border:1px solid #ccd3dd; border-radius:4px; padding:2px 7px; background:white; color:#334155; }
button[aria-pressed="true"] { background:#334155; color:white; }
button:focus-visible { outline:2px solid #2563eb; outline-offset:2px; }
svg { width:100%; display:block; }
.y-slider .track { stroke:#e4e3de; stroke-width:4; stroke-linecap:round; }
.y-slider .selected { stroke:#94a3b8; stroke-width:4; stroke-linecap:round; }
.y-slider .knob { fill:white; stroke:#334155; stroke-width:1.5; cursor:ns-resize; touch-action:none; }
.dots { margin-left:12px; }
svg text { font:9px 'DejaVu Sans',sans-serif; fill:#596273; }
svg .axis-title { font-size:10px; }
.chart-legend { display: flex; flex-wrap: wrap; gap: 8px 18px; list-style: none; padding: 0; margin: 8px 0; font-size: 11px; }
.chart-legend li { display: flex; gap: 5px; align-items: center; }
.chart-legend li span { width: 16px; height: 3px; flex-shrink: 0; }
.full-width svg text { font-size:12px; }
.full-width svg .axis-title { font-size:13px; }
.full-width svg [data-cell] > path { stroke-width:0.75; }
.window-boundary line { stroke:#334155; stroke-width:3; }
.window-boundary text { fill:#334155; font-weight:700; }
.series-dimmed { opacity:.15; }
.full-width svg .series-highlighted > path { stroke-width:2; }
.legend-fork:hover,.legend-fork:focus-visible { background:#eef2f6;outline:1px solid currentColor; }
.window-chart-legend { position:absolute;top:4px;right:4px;display:flex;gap:10px;max-width:calc(100% - 125px);overflow-x:auto;padding:6px;border-radius:6px;background:rgba(255,255,255,.94);font-size:12px; }
.legend-window { display:flex;flex-direction:column;gap:4px;min-width:100px; }
.legend-window > strong { text-align:center; }
.legend-fork { display:flex;align-items:center;gap:5px;border:1px solid;border-radius:4px;padding:3px 5px;white-space:nowrap; }
.legend-fork.continues { border-width:2px;background:#f0fdf4; }
.continuation-label { color:#15803d;font-size:9px; }
.legend-fork > span { width:8px;height:8px;border-radius:2px; }
.legend-fork > small { margin-left:auto;font-variant-numeric:tabular-nums; }
.outcome-legend { margin:0; font-size:14px; }
.full-width .filters, .full-width .chart-legend { font-size:14px; }
</style>
