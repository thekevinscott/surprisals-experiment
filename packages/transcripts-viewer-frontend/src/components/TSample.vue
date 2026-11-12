<script setup>
import { inject,computed } from 'vue'
import {fetchJson,useLiveResource} from '../composables/api.js'
import PassBlocks from './PassBlocks.vue'
import { attemptState, attemptOutcome } from '../composables/outcomes.js'
import ContentPanel from './ContentPanel.vue'
import Button from 'primevue/button'
import {sampleFiles} from '../composables/sampleFiles.js'
import {openFiles} from '../composables/filePreview.js'
import TranscriptButton from './TranscriptButton.vue'
const props=defineProps({ sample: Object })
const apiUrl=inject('apiUrl')
const rawUrl=inject('rawSourceUrl')
const {data,loading,error}=useLiveResource(()=>[apiUrl(props.sample.source)],(signal,[url])=>fetchJson(url,signal))
const latest=computed(()=>data.value?.attempts.find(attempt=>attempt.id===props.sample.latest?.id) ?? props.sample.latest)
const files=computed(()=>sampleFiles(data.value?.attempts ?? [],rawUrl))
</script>
<template>
  <ContentPanel local :collapsible="false" class="t-sample" :data-sample="sample.id" :title="`T${sample.id}`">
    <template #title><span class="sample-label" :class="attemptOutcome(sample.latest)">T{{ sample.id }}</span></template>
    <template #actions><Button text size="small" label="📄" aria-label="Open files" title="Open files" :disabled="!files.length" @click="openFiles({name:`T${sample.id} files`,files})" /><TranscriptButton v-if="data?.attempts.length" :files="data.attempts.flatMap(attempt => attempt.transcriptFiles ?? [])" label="💬" /></template>
    <div class="sample-tests">
      <PassBlocks v-if="latest?.tests && !latest.generation?.timed_out && !latest.generation?.error" :passed="latest.tests.passed" :total="latest.tests.total" :cases="latest.tests.cases" :source="latest.testsSource" />
      <span v-else>{{ attemptState(sample.latest) }}</span>
    </div>
    <p v-if="loading">Loading…</p><p v-else-if="error" role="alert">{{ error }}</p>
  </ContentPanel>
</template>
<style scoped>
.t-sample { container-type: inline-size; min-width: 0; margin: 0; background: #f8fafc; border: 1px solid #d0dae7; border-radius: 6px; }
.sample-label.passed { color: #15803d; }
.sample-label.failed { color: #b91c1c; }
.sample-label.unknown { color: #657186; }
.sample-tests { display: flex; justify-content: center; align-items: center; min-width: 0; margin: 2px 0 4px; font-size: 10px; overflow-wrap: anywhere; }
.t-sample :deep(.p-panel-header) { flex-wrap: nowrap; align-items: flex-start; gap: 0; padding: 2px; }
.t-sample :deep(.p-panel-header-actions) { flex-wrap: nowrap; flex-shrink: 0; }
.t-sample :deep(.panel-label) { flex: 1; flex-wrap: nowrap; gap: 2px; align-self: center; }
.t-sample :deep(.p-panel-header .p-button) { padding: 2px; }
.t-sample :deep(.p-panel-toggle-button) { width: 18px; height: 18px; }
.t-sample :deep(.p-panel-content) { padding: 0 2px 2px; }
@container (max-width: 56px) {
  .t-sample :deep(.p-panel-header) { flex-direction: column; align-items: center; padding: 1px; }
  .t-sample :deep(.p-panel-header-actions) { order: -1; justify-content: center; width: 100%; }
  .t-sample :deep(.p-panel-header .p-button) { width: 12px; min-width: 0; height: 18px; padding: 0; font-size: 10px; }
}
p { font-size: 11px; color: #657186; }
</style>
