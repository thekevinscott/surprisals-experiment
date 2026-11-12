<script setup>
import { computed, ref } from 'vue'
const props=defineProps({chartData:Object})

const armSel = ref(props.chartData.arms[0])
const unit = computed(() => armSel.value === 'surprisal' ? 'bits' : 'chars')
const runs = computed(()=>props.chartData.wait)
const mode = ref('all')
const focus = ref(null)
const hover = ref(null)

const width = 840
const values = computed(() => series.value.flatMap(s => [...s.bests.map(b => b[1]), ...(s.pending[0] ? [s.pending[0]] : [])]))
const xmin = computed(() => Math.min(...values.value, 1e9) / 1.3)
const xmax = computed(() => Math.max(...values.value, 1) * 1.3)
const x = v => (Math.log(xmax.value) - Math.log(v)) / (Math.log(xmax.value) - Math.log(xmin.value)) * width
const y = v => 240 - Math.sqrt(v / Math.max(50, ...series.value.flatMap(s => [...s.bests.map(b => b[2]), s.pending[1]]))) * 220
const xticks = computed(() => [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000].filter(t => t >= xmin.value && t <= xmax.value))
const yticks = [0, 1, 2, 5, 10, 20, 50]
const armRuns = computed(() => runs.value.filter(r => r.strategy === armSel.value))
const modes = computed(() => ['all', ...new Set(armRuns.value.map(r => r.problem))])
const series = computed(() => armRuns.value.filter(r => mode.value === 'all' || r.problem === mode.value))
const opacity = s => focus.value && focus.value !== s.cell ? 0.12 : 1
const describe = (s, b) => `${s.problem} ${s.cell} · turn ${b[0]} · new best ${b[1].toLocaleString(undefined, {maximumFractionDigits: 1})} ${unit.value} · ${b[2]} turns without improvement before it`
const describePending = s => `${s.problem} ${s.cell} · ${s.pending[1]} turns since last best (${s.pending[0].toLocaleString(undefined, {maximumFractionDigits: 1})} ${unit.value}), no new best yet`
</script>

<template>
  <div class="wait-chart" @mouseleave="hover = null; focus = null" @pointerdown.stop @click.stop @dblclick.stop>
    <div class="filters" @click.stop @keydown.stop>
      <span>Strategy</span>
      <button v-for="value in chartData.arms" :key="value" :aria-pressed="armSel === value" @click="armSel = value; mode = 'all'">{{ value }}</button>
      <span style="margin-left:12px">Problem</span>
      <button v-for="value in modes" :key="value" :aria-pressed="mode === value" @click="mode = value">{{ value }}</button>
      <span class="tooltip" role="status">{{ hover || 'Hover a point or legend entry' }}</span>
    </div>
    <svg viewBox="0 0 960 285" role="img" aria-label="Unsuccessful turns before each new best, by its length">
      <text x="32" y="135" transform="rotate(-90 32 135)" text-anchor="middle" class="axis-title">Turns without improvement before it (depth, sqrt)</text>
      <g transform="translate(70,0)">
        <g v-for="t in yticks" :key="t">
          <line x1="0" :x2="width" :y1="y(t)" :y2="y(t)" stroke="#e4e3de" />
          <text x="-8" :y="y(t) + 3" text-anchor="end">{{ t }}</text>
        </g>
        <text v-for="t in xticks" :key="t" :x="x(t)" y="255" text-anchor="middle">{{ t.toLocaleString() }}</text>
        <text :x="width / 2" y="271" text-anchor="middle" class="axis-title">New best advice ({{ unit }}, log) · right = shorter</text>
        <g v-for="s in series" :key="s.cell" :style="{ opacity: opacity(s) }" @mouseenter="focus = s.cell">
          <circle v-for="(b, i) in s.bests" :key="i" :cx="x(b[1])" :cy="y(b[2])" r="2.4" :fill="s.color" fill-opacity="0.7"
            @mouseenter="hover = describe(s, b)"><title>{{ describe(s, b) }}</title></circle>
          <circle v-if="s.pending[1]" :cx="x(s.pending[0])" :cy="y(s.pending[1])" r="3.5" fill="white" :stroke="s.color" stroke-width="1.5"
            @mouseenter="hover = describePending(s)"><title>{{ describePending(s) }}</title></circle>
        </g>

      </g>
    </svg>
    <ul class="chart-legend">
      <li v-for="s in series" :key="s.cell"><span :style="{background:s.color}"></span>{{ s.problem }} {{ s.cell.split('-').slice(2).join('-') }}</li>
    </ul>
  </div>
</template>

<style scoped>
.wait-chart { width: 100%; margin: 4px 0; }
.filters { display:flex; align-items:center; gap:5px; font-size:11px; min-height:30px; flex-wrap:wrap; }
button { border:1px solid #ccd3dd; border-radius:4px; padding:2px 7px; background:white; color:#334155; }
button[aria-pressed="true"] { background:#334155; color:white; }
.tooltip { margin-left:auto; font-size:10px; color:#475569; }
svg { width:100%; display:block; }
svg text { font:9px 'DejaVu Sans',sans-serif; fill:#596273; }
svg .axis-title { font-size:10px; }
svg .legend { font-size:8px; }
.legend-item { cursor:default; }
.chart-legend { display: flex; flex-wrap: wrap; gap: 8px 18px; list-style: none; padding: 0; margin: 8px 0; font-size: 11px; }
.chart-legend li { display: flex; gap: 5px; align-items: center; }
.chart-legend li span { width: 16px; height: 3px; flex-shrink: 0; }
</style>
