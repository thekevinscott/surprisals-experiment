<script setup>
import { computed } from 'vue'
import { visibleEnds } from '../composables/visibleEnds.js'
import Button from 'primevue/button'
import TurnBlock from './TurnBlock.vue'
const props = defineProps({ fork: Object, continues: Boolean, turnIds: Array, expanded: Boolean, canExpand: Boolean })
defineEmits(['toggle'])
const visibleTurns = computed(() => visibleEnds(props.fork.parallel, props.expanded))
const rowFor = id => props.turnIds.indexOf(id) + 2 + (props.canExpand && !props.expanded && props.turnIds.indexOf(id) > 0 ? 1 : 0)
</script>
<template>
  <section class="fork-branch" :class="{ continues }" :data-fork="fork.id">
    <div class="fork-heading"><strong>Fork {{ fork.id }}</strong><small v-if="continues">Continues ↓</small></div>
    <div class="turns"><TurnBlock v-for="turn in visibleTurns" :key="turn.id" :turn="turn" :style="{ gridRow: rowFor(turn.id) }" /></div>
    <Button text size="small" v-if="canExpand && !expanded" class="ellipsis" :style="{ gridRow: 3 }" :label="`Show ${fork.parallel.length - 2} hidden turns`" @click="$emit('toggle')" />
    <p v-if="!fork.parallel.length">No turns recorded</p>
  </section>
</template>
<style scoped>
.fork-branch { position: relative; display: grid; grid-template-rows: subgrid; grid-row: 1 / span var(--parallel-rows); min-width: 0; margin: 0; padding: 0 3px 3px; background: #f8fafd; border: 1px solid #dce3ee; border-radius: 8px; }
.fork-heading { display: flex; gap: 8px; align-items: center; min-height: 26px; padding: 3px 2px; line-height: 18px; }
.continues { background: #edf7f2; border-color: #70a88b; }
strong { font-size: 12px; }
small { white-space: nowrap; color: #47745b; font-size: 10px; }
.turns { display: contents; }
.turns > :deep(.turn-block) { align-self: center; }
p { font-size: 11px; color: #657186; }
</style>
