<script setup>
import { computed, ref, useId } from 'vue'

const props = defineProps({ chartData:Object, kind: { type: String, required: true } })
const armSel = ref(props.chartData.arms[0])
const unit = computed(() => armSel.value === 'surprisal' ? 'bits' : 'characters')
const mode = ref('all')
const data = computed(()=>props.chartData.series)
const domains = computed(()=>props.chartData.domains)
const range = ref(null)
const knob = ref(null)
const clipId = useId()
const dots = ref(true)
const logarithmic = ref(false)
const exitOf = s => s.exit_code ?? undefined
const statusMark = s => s.running ? '?' : exitOf(s) === 0 ? '✓' : '✕'
const endPoint = s => props.kind === 'advice' ? s.advice.at(-1) : s.streak[0]

const width = 840
const selected = computed(() => data.value.filter(s => s.strategy === armSel.value))
const modes = computed(() => ['all', ...new Set(selected.value.map(s => s.problem))])
const visible = computed(() => selected.value.filter(s => mode.value === 'all' || s.problem === mode.value))
const chartKey = computed(() => props.kind === 'advice' && unit.value === 'bits' ? 'surprisal' : props.kind)
const points = s => s[props.kind]
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
const xticks = computed(() => Array.from({length: Math.floor(domain.value.x[1] / 10) + 1}, (_, i) => i * 10))
const x = v => (v-domain.value.x[0]) / (domain.value.x[1]-domain.value.x[0]) * width
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
  return points(s).map((p, i) => `${i ? (props.kind === 'advice' ? 'H' + x(p[0]) + 'V' : 'L' + x(p[0]) + ',') : 'M' + x(p[0]) + ','}${y(p[1])}`).join(' ')
}
</script>

<template>
  <div class="cell-chart" :data-kind="kind" @pointerdown.stop @pointermove.stop @pointerup.stop @pointercancel.stop @click.stop @dblclick.stop>
    <div class="filters" @click.stop @keydown.stop>
      <span>Strategy</span>
      <button v-for="value in chartData.arms" :key="value" :aria-pressed="armSel === value" @click="armSel = value; mode = 'all'; range = null">{{ value }}</button>
      <span style="margin-left:12px">Problem</span>
      <button v-for="value in modes" :key="value" :aria-pressed="mode === value" :data-mode="value" @click="mode = value">{{ value }}</button>
      <button v-if="kind === 'advice'" :aria-pressed="logarithmic" @click="logarithmic = !logarithmic">Log (1 + score)</button>
      <button v-if="kind === 'advice'" class="dots" :aria-pressed="dots" @click="dots = !dots">all passing turns</button>
    </div>
    <svg viewBox="0 0 960 285" role="img" :aria-label="`${kind} by cell`">
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
      <text x="32" y="135" transform="rotate(-90 32 135)" text-anchor="middle" class="axis-title">{{ kind === 'advice' ? (unit === 'bits' ? 'Advice surprisal (bits)' : 'Advice characters (linear)') : 'Turns since previous improvement' }}</text>
      <g transform="translate(95,0)" data-plot="shared">
        <g v-for="tick in yticks" :key="tick">
          <line x1="0" :x2="width" :y1="y(tick)" :y2="y(tick)" stroke="#e4e3de" />
          <text x="-8" :y="y(tick) + 3" text-anchor="end">{{ tick.toLocaleString() }}</text>
        </g>
        <g v-for="tick in xticks" :key="tick">
          <text :x="x(tick)" y="255" text-anchor="middle">{{ tick }}</text>
        </g>
        <text :x="width / 2" y="271" text-anchor="middle" class="axis-title">Turn (sequential depth)</text>
        <line v-if="kind === 'improvements' && ymin <= 50 && ymax >= 50" x1="0" :x2="width" :y1="y(50)" :y2="y(50)" stroke="#777" stroke-dasharray="2 3" />
        <g :clip-path="`url(#${clipId})`">
        <g v-for="s in visible" :key="s.cell" :data-cell="s.cell" :data-mode="s.problem">
          <circle v-for="(p, i) in (!dots ? [] : kind === 'advice' ? s.passing : s.improvements).filter(p => p[1] >= ymin && p[1] <= ymax)" :key="`point-${i}`" :cx="x(p[0])" :cy="y(p[1])" :r="kind === 'advice' ? 1.4 : 2" :fill="s.color" :opacity="kind === 'advice' ? .25 : 1" />
          <path :d="path(s)" fill="none" :stroke="s.color" stroke-width="0.5" />
          <text v-if="endPoint(s)" :x="x(endPoint(s)[0]) + 2" :y="y(endPoint(s)[1]) + 2.5" :class="exitOf(s) === 0 ? 'exit-ok' : 'exit-fail'" :style="exitOf(s) === 0 ? null : { fill: s.color }">{{ statusMark(s) }}</text>
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
    <ul class="chart-legend">
      <li v-for="s in visible" :key="s.cell"><span :style="{background:s.color}"></span>{{ s.problem }} {{ s.cell.split('-').slice(2).join('-') }}{{ kind === 'advice' ? (s.advice.length ? ` · ${s.advice.at(-1)[1].toLocaleString(undefined,{maximumFractionDigits:1})}` : ' · no all-samples pass') : '' }} {{ statusMark(s) }}</li>
    </ul>
  </div>
</template>

<style scoped>
.cell-chart { width: 100%; margin: 4px 0; }
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
svg .legend { font-size:8px; }
svg .exit-ok { fill:#15803d; font-size:8px; font-weight:700; }
svg .exit-fail { font-size:7px; }
svg .legend .exit-ok, svg .legend .exit-fail { font-size:7px; }
.chart-legend { display: flex; flex-wrap: wrap; gap: 8px 18px; list-style: none; padding: 0; margin: 8px 0; font-size: 11px; }
.chart-legend li { display: flex; gap: 5px; align-items: center; }
.chart-legend li span { width: 16px; height: 3px; flex-shrink: 0; }
</style>
