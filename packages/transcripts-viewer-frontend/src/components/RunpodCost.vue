<script setup>
import {computed} from 'vue'
import {fetchJson,useLiveResource} from '../composables/api.js'
import {runpodCost,runpodTooltip} from '../composables/runpodCost.js'
const props=defineProps({now:Number})
const {data:pods,error}=useLiveResource(()=>['/api/runs/runpod-costs'],(signal,urls)=>fetchJson(urls[0],signal))
const total=computed(()=>runpodCost(pods.value??[],props.now))
const money=value=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(value)
</script>
<template>
  <aside v-if="pods?.length || error" class="runpod-cost" :title="error || runpodTooltip(pods)">
    <template v-if="error">RunPod cost unavailable</template>
    <template v-else>RunPod {{ money(total) }} <small>estimate · compute only</small></template>
  </aside>
</template>
<style scoped>
.runpod-cost { position:fixed;top:8px;right:28px;z-index:999;padding:6px 10px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:#334155;font-size:12px;box-shadow:0 1px 4px #0001;font-variant-numeric:tabular-nums; }
.runpod-cost small { margin-left:6px;color:#64748b; }
</style>
