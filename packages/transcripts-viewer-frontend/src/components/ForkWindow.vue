<script setup>
import { computed, ref, inject, watch, nextTick, onMounted } from 'vue'
import ContentPanel from './ContentPanel.vue'
import ForkBranch from './ForkBranch.vue'
import TurnBlock from './TurnBlock.vue'
const props = defineProps({ window: Object, target: Object, hasNext: Boolean })
const link = inject('runLink')
const sampleCount = inject('sampleCount')
const windowExpanded = ref(true)
const windowPanel = ref(null)
const turnIds = computed(() => [...new Set(props.window.forks.flatMap(f => f.parallel.map(t => t.id)))].sort((a,b) => a-b))
const columnWidth = computed(() => (sampleCount() || Math.max(1, ...props.window.forks.flatMap(f => [...f.parallel,...f.solo].map(t=>t.samples.length)))) * 72 + 16)
async function reveal(target) {
  if (String(props.window.id) !== target?.window) return
  windowExpanded.value = true
  await nextTick()
  windowPanel.value?.setExpanded(true)
}
watch(() => props.target, reveal, { deep:true })
onMounted(() => reveal(props.target))
defineExpose({ reveal })
</script>
<template>
  <ContentPanel ref="windowPanel" v-model:expanded="windowExpanded" class="run-window" :data-window="window.id" :title="`Window ${window.id}`" :href="link(`windows/${window.id}`)">
    <div class="window-grid" :style="{ '--fork-count': Math.max(1, window.forks.length), '--parallel-rows': turnIds.length + 2, '--fork-width': `${columnWidth}px` }">
      <div class="phase fork-phase" role="group" aria-label="Parallel forks">
        <ForkBranch v-for="(fork,index) in window.forks" :key="fork.id" :fork="fork" :window-id="window.id" :turn-ids="turnIds" :style="{ gridColumn: index + 1 }" :continues="window.continuedForks.includes(fork.id)" />
      </div>
      <div v-if="window.continuedForks.length" class="phase solo-phase" role="group" aria-label="Solo continuation">
        <template v-for="(fork,index) in window.forks" :key="fork.id">
          <div v-if="fork.solo.length" class="solo" :style="{ gridColumn: index + 1 }" :data-continuation="fork.id" :data-fork="fork.id">
            <h3>Fork {{ fork.id }} continues</h3>
            <TurnBlock v-for="turn in fork.solo" :key="turn.id" :turn="turn" />
          </div>
        </template>
      </div>
    </div>
    <div v-if="hasNext" class="next-window">{{ window.continuedForks.length ? `Fork ${window.continuedForks.join(', ')} → next window` : 'Next recorded window' }}</div>
  </ContentPanel>
</template>
<style scoped>
.run-window { margin: 0 0 8px; background: var(--viewer-gray); }
.phase { display: grid; grid-template-columns: repeat(var(--fork-count), minmax(var(--fork-width), 1fr)); gap: 8px; }
.fork-phase { grid-template-rows: repeat(var(--parallel-rows), auto); }
.solo-phase { margin-top: 8px; }
.solo { display: grid; gap: 8px; padding: 4px; border: 1px solid var(--viewer-green-border); background: var(--viewer-green); border-radius: 8px; }
h3 { font-size: 12px; line-height: 16px; margin: 0; color: var(--viewer-muted); }
.next-window { margin: 8px 0; padding-top: 8px; border-top: 1px solid var(--viewer-border); text-align: center; font-size: 12px; color: var(--viewer-muted); }
</style>
