<script setup>
import { computed, ref, inject, watch, nextTick, onMounted } from 'vue'
import SourceActions from './SourceActions.vue'
import ContentPanel from './ContentPanel.vue'
import { useColumnLayout } from '../composables/useColumnLayout.js'
import { visibleEnds } from '../composables/visibleEnds.js'
import Button from 'primevue/button'
import ForkBranch from './ForkBranch.vue'
import TurnBlock from './TurnBlock.vue'
const props = defineProps({ window: Object, target: Object, hasNext: Boolean })
const link = inject('runLink')
const columns = useColumnLayout(computed(() => props.window.forks))
const windowExpanded = ref(true)
const windowPanel = ref(null)
const forksExpanded = ref(false)
const soloExpanded = ref(false)
const forkPhase = ref(null)
const soloPhase = ref(null)
const canExpandForks = computed(() => props.window.forks.some(f => f.parallel.length > 2))
const visibleTurnIds = computed(() => [...new Set(props.window.forks.flatMap(f => visibleEnds(f.parallel, forksExpanded.value).map(t => t.id)))].sort((a, b) => a - b))
const parallelRows = computed(() => visibleTurnIds.value.length + 1 + (canExpandForks.value && !forksExpanded.value ? 1 : 0))
const visibleSolo = fork => visibleEnds(fork.solo, soloExpanded.value)
const toggleForks = () => forkPhase.value.toggle()
const toggleSolo = () => soloPhase.value.toggle()
async function reveal(target) {
  if (String(props.window.id) !== target?.window) return
  windowExpanded.value = true
  await nextTick()
  windowPanel.value?.setExpanded(true)
  if (target.turn != null) {
    forkPhase.value?.setExpanded(true)
    soloPhase.value?.setExpanded(true)
    columns.reset()
  }
  await nextTick()
}
watch(() => props.target, reveal, { deep:true })
onMounted(() => reveal(props.target))
defineExpose({ reveal })
</script>
<template>
  <ContentPanel ref="windowPanel" v-model:expanded="windowExpanded" class="run-window" :data-window="window.id" :title="`Window ${window.id}`" :href="link(`windows/${window.id}`)">
    <div class="window-grid" :style="{ '--fork-count': Math.max(1, window.forks.length), '--parallel-rows': parallelRows }">
      <ContentPanel ref="forkPhase" v-model:expanded="forksExpanded" title="Forks" expand-label="All turns" collapse-label="First & last" preview :collapsible="canExpandForks">
      <div v-if="columns.hidden.value.length" class="collapsed-forks"><span>Collapsed to make room:</span><button v-for="fork in columns.hidden.value" :key="fork.id" @click="columns.reset()">Fork {{ fork.id }} · restore</button></div>
      <div class="phase fork-phase" role="group" aria-label="Parallel forks">
      <template v-for="(fork, index) in window.forks" :key="fork.id">
        <ForkBranch v-if="columns.isVisible(index)" :fork="fork" :turn-ids="visibleTurnIds" :expanded="forksExpanded" :can-expand="canExpandForks" @toggle="toggleForks" :style="columns.columnStyle(index)" :continues="window.continuedForks.includes(fork.id)" :span="columns.columnSpan(index)" :max-span="window.forks.length - index" @resize="columns.resize(index, $event)" />
      </template>
      </div>
      </ContentPanel>
      <div v-if="window.continuedForks.length" class="connector" aria-hidden="true">↓</div>
      <ContentPanel v-if="window.continuedForks.length" ref="soloPhase" v-model:expanded="soloExpanded" title="Solo" expand-label="All turns" collapse-label="First & last" preview :collapsible="window.forks.some(f => f.solo.length > 2)" class="solo-section">
      <div class="phase solo-phase" role="group" aria-label="Solo continuation">
      <template v-for="(fork, index) in window.forks" :key="`solo-${fork.id}`">
        <div v-if="fork.solo.length" class="solo" :style="columns.isVisible(index) ? columns.columnStyle(index) : { gridColumn: '1 / -1' }" :data-continuation="fork.id" :data-fork="fork.id">
          <h3>Fork {{ fork.id }} continues</h3>
          <template v-for="(turn, turnIndex) in visibleSolo(fork)" :key="turn.id">
            <TurnBlock :turn="turn" />
            <Button text size="small" v-if="fork.solo.length > 2 && !soloExpanded && turnIndex === 0" class="ellipsis" :label="`Show ${fork.solo.length - 2} hidden turns`" @click="toggleSolo" />
          </template>
        </div>
      </template>
      </div>
      </ContentPanel>
    </div>
    <ContentPanel title="Original U transcript files">
      <p v-for="fork in window.forks" :key="fork.id">Fork {{ fork.id }} · transcript.jsonl <SourceActions :source="fork.transcriptPath" /></p>
    </ContentPanel>
    <p v-if="!window.continuedForks.length" class="note">No solo continuation recorded in this window.</p>
    <div v-if="hasNext" class="next-window">{{ window.continuedForks.length ? `Fork ${window.continuedForks.join(', ')} → next window` : 'Next recorded window' }}<div aria-hidden="true">↓</div></div>
  </ContentPanel>
</template>
<style scoped>
.run-window { margin: 0 0 8px; background: #f8fafd; }
.phase { position: relative; display: grid; grid-template-columns: repeat(var(--fork-count), minmax(180px, 1fr)); gap: 6px 10px; padding: 0; }
.solo-section { margin-top: 0; border-color: #a3c4b4; }
.fork-phase { grid-template-rows: repeat(var(--parallel-rows), auto); }

.solo { display: grid; gap: 6px; padding: 0 3px 3px; border: 1px solid #70a88b; border-top: 0; background: #edf7f2; border-radius: 0 0 8px 8px; }
h3 { font-size: 12px; margin: 0; color: #47745b; }
.connector { text-align: center; color: #5872a5; font-size: 22px; }
.next-window { margin: 12px 0 24px; padding: 12px 0 0; border-top: 1px solid #829bbd; text-align: center; font-size: 12px; color: #365f9b; }
.next-window div { font-size: 24px; }
.collapsed-forks { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; font-size: 11px; color: #657186; }
.collapsed-forks button { border: 1px solid #bac7d9; border-radius: 5px; padding: 5px 8px; background: white; color: #214da3; cursor: pointer; }
.note { color: #657186; font-size: 12px; }
</style>
