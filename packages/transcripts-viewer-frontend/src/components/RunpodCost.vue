<script setup>
import {computed} from 'vue'
import {fetchJson,useLiveResource} from '../composables/api.js'
import {experimentCost,costTooltip} from '../composables/experimentCost.js'
import {runpodCost,runpodTooltip} from '../composables/runpodCost.js'
const props=defineProps({now:Number,showTotal:Boolean})
const {data:pods,error}=useLiveResource(()=>['/api/runs/runpod-costs'],(signal,urls)=>fetchJson(urls[0],signal))
const {data:runs,error:costError}=useLiveResource(()=>props.showTotal ? ['/api/runs/costs'] : [],(signal,urls)=>fetchJson(urls[0],signal))
const breakdown=computed(()=>experimentCost(runs.value?.rows??[],pods.value??[],props.now))
const total=computed(()=>runpodCost(pods.value??[],props.now))
const money=value=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(value)
</script>
<template>
  <div class="experiment-costs">
  <aside v-if="showTotal" class="total-cost" :title="costError || error || (runs && pods ? costTooltip(breakdown,pods,runs.warnings) : undefined)">
    <template v-if="costError || error">Total cost unavailable</template>
    <template v-else-if="!runs || !pods">Total cost loading…</template>
    <template v-else>Total cost {{ money(breakdown.total) }} <small>estimate</small></template>
  </aside>
  <aside v-if="pods?.length || error" class="runpod-cost" :title="error || runpodTooltip(pods)">
    <template v-if="error">RunPod cost unavailable</template>
    <template v-else>RunPod {{ money(total) }} <small>estimate · compute only</small></template>
  </aside>
  </div>
</template>
<style scoped>
.experiment-costs { position:fixed;top:8px;right:28px;z-index:999;display:flex;gap:8px; }
.experiment-costs aside { padding:6px 10px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:#334155;font-size:12px;box-shadow:0 1px 4px #0001;font-variant-numeric:tabular-nums; }
.experiment-costs small { margin-left:6px;color:#64748b; }
</style>
