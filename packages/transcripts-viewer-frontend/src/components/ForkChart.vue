<script setup>
import {computed,inject,ref} from 'vue'
import ContentPanel from './ContentPanel.vue'
import CellChart from './CellChart.vue'
const props=defineProps({windowId:Number,forkId:Number,solo:Boolean})
const chartFor=inject('forkChart')
const openChartTurn=inject('openChartTurn')
const chart=computed(()=>chartFor(props.windowId,props.forkId,props.solo))
const expanded=ref(true)
</script>
<template>
  <ContentPanel local v-model:expanded="expanded" class="fork-chart" title="Advice" :state-key="`fork-chart-${windowId}-${forkId}-${solo ? 'solo' : 'parallel'}`"><CellChart :x-zoom="false" all-points clickable @open-turn="openChartTurn" :state-key="`fork-${windowId}-${forkId}-${solo ? 'solo' : 'parallel'}`" range-key="forks" :chart-data="chart" :plot-width="360" kind="advice" :controls="false" /></ContentPanel>
</template>
<style scoped>
.fork-chart { align-self:start; }
.fork-chart :deep(.cell-chart) { height:208px;margin:0; }
.fork-chart :deep(.filters),.fork-chart :deep(.chart-legend) { display:none; }
.fork-chart :deep(.cell-chart svg) { width:100%;height:208px; }
.fork-chart :deep(.cell-chart svg text) { font-size:14px; }
.fork-chart :deep(.cell-chart svg [data-cell] > path) { stroke-width:2px;vector-effect:non-scaling-stroke; }
</style>
