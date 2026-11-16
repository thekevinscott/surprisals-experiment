<script setup>
import {computed} from 'vue'
import {fetchJson,useLiveResource} from '../composables/api.js'
import {costTooltip} from '../composables/experimentCost.js'
import {runpodTooltip} from '../composables/runpodCost.js'
const props=defineProps({showTotal:Boolean})
const {data:runs,error}=useLiveResource(()=>['/api/runs/costs'],(signal,urls)=>fetchJson(urls[0],signal))
const pods=computed(()=>runs.value?.pods)
const breakdown=computed(()=>runs.value?.breakdown)
const total=computed(()=>breakdown.value?.runpod)
const money=value=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(value)
</script>
<template>
  <div class="experiment-costs">
  <aside v-if="showTotal" class="total-cost" :title="error || (runs && pods ? costTooltip(breakdown,pods,runs.warnings) : undefined)">
    <template v-if="error">Total cost unavailable</template>
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
.experiment-costs aside { padding:6px 10px;border:1px solid var(--viewer-border);border-radius:6px;background:var(--viewer-surface);color:var(--viewer-text);font-size:12px;box-shadow:0 1px 4px #0001;font-variant-numeric:tabular-nums; }
.experiment-costs small { margin-left:6px;color:var(--viewer-muted); }
</style>
