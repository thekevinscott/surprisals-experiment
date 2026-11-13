<script setup>
import {computed,inject,ref} from 'vue'
import ContentPanel from './ContentPanel.vue'
import CellChart from './CellChart.vue'
import TurnBlock from './TurnBlock.vue'
const props = defineProps({ fork: Object, windowId: Number, continues: Boolean, turnIds: Array })
const chartFor=inject('forkChart')
const chart=computed(()=>chartFor(props.windowId,props.fork.id))
const chartExpanded=ref(true)
const rowFor = id => props.turnIds.indexOf(id) + 3
</script>
<template>
  <section class="fork-branch" :class="{ continues }" :data-fork="fork.id">
    <div class="fork-heading"><strong>Fork {{ fork.id }}</strong><small v-if="continues">Continues ↓</small></div>
    <ContentPanel local v-model:expanded="chartExpanded" class="fork-chart" title="Advice" :state-key="`fork-chart-${windowId}-${fork.id}`"><CellChart :chart-data="chart" :plot-width="360" kind="advice" :controls="false" /></ContentPanel>
    <div class="turns"><TurnBlock v-for="turn in fork.parallel" :key="turn.id" :turn="turn" :style="{ gridRow: rowFor(turn.id) }" /></div>
    <p v-if="!fork.parallel.length">No turns recorded</p>
  </section>
</template>
<style scoped>
.fork-branch { position: relative; display: grid; grid-template-rows: subgrid; grid-row: 1 / span var(--parallel-rows); min-width: 0; margin: 0; padding: 0 4px 4px; background: var(--viewer-gray); border: 1px solid var(--viewer-border); border-radius: 8px; }
.fork-heading { display: flex; gap: 8px; align-items: center; min-height: 24px; padding: 4px 0; line-height: 16px; }
.fork-chart { grid-row:2;align-self:start; }
.fork-chart :deep(.cell-chart) { height:208px;margin:0; }
.fork-chart :deep(.filters),.fork-chart :deep(.chart-legend) { display:none; }
.fork-chart :deep(.cell-chart svg) { width:100%;height:208px; }
.fork-chart :deep(.cell-chart svg text) { font-size:14px; }
.fork-chart :deep(.cell-chart svg [data-cell] > path) { stroke-width:2px;vector-effect:non-scaling-stroke; }
.continues { background: var(--viewer-green); border-color: var(--viewer-green-border); }
strong { font-size: 12px; }
small { white-space: nowrap; color: var(--viewer-muted); font-size: 10px; }
.turns { display: contents; }
.turns > :deep(.turn-block) { align-self: center; }
p { font-size: 12px; color: var(--viewer-muted); }
</style>
