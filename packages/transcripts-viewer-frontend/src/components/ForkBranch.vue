<script setup>
import ForkChart from './ForkChart.vue'
import TurnBlock from './TurnBlock.vue'
const props = defineProps({ fork: Object, windowId: Number, continues: Boolean, turnIds: Array })
const rowFor = id => props.turnIds.indexOf(id) + 3
</script>
<template>
  <section class="fork-branch" :class="{ continues }" :data-fork="fork.id">
    <div class="fork-heading"><strong>Fork {{ fork.id }}</strong><small v-if="continues">Continues ↓</small></div>
    <ForkChart :window-id="windowId" :fork-id="fork.id" />
    <div class="turns"><TurnBlock v-for="turn in fork.parallel" :key="turn.id" :turn="turn" :style="{ gridRow: rowFor(turn.id) }" /></div>
    <p v-if="!fork.parallel.length">No turns recorded</p>
  </section>
</template>
<style scoped>
.fork-branch { position: relative; display: grid; grid-template-rows: subgrid; grid-row: 1 / span var(--parallel-rows); min-width: 0; margin: 0; padding: 0 4px 4px; background: var(--viewer-gray); border: 1px solid var(--viewer-border); border-radius: 8px; }
.fork-heading { display: flex; gap: 8px; align-items: center; min-height: 24px; padding: 4px 0; line-height: 16px; }
.fork-chart { grid-row:2; }
.continues { background: var(--viewer-green); border-color: var(--viewer-green-border); }
strong { font-size: 12px; }
small { white-space: nowrap; color: var(--viewer-muted); font-size: 10px; }
.turns { display: contents; }
.turns > :deep(.turn-block) { align-self: center; }
p { font-size: 12px; color: var(--viewer-muted); }
</style>
