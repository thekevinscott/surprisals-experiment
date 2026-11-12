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
const status=computed(()=>error.value || (loading.value?'Loading…':attemptState(latest.value)))
const files=computed(()=>sampleFiles(data.value?.attempts ?? [],rawUrl))
</script>
<template>
  <ContentPanel local :collapsible="false" class="t-sample" :data-sample="sample.id" :title="`T${sample.id}`">
    <template #title><span class="sample-label" :class="attemptOutcome(sample.latest)">T{{ sample.id }}</span></template>
    <template #actions><Button class="icon-button" text size="small" label="📄" aria-label="Open files" title="Open files" :disabled="!files.length" @click="openFiles({name:`T${sample.id} files`,files})" /><TranscriptButton v-if="data?.attempts.length" :files="data.attempts.flatMap(attempt => attempt.transcriptFiles ?? [])" :modal-title="`T${sample.id} transcript`" label="💬" /></template>
    <div class="sample-tests">
      <PassBlocks v-if="latest?.tests?.cases" :passed="latest.tests.passed" :total="latest.tests.total" :cases="latest.tests.cases" :source="latest.testsSource" />
      <span v-else :title="status">{{ status }}</span>
    </div>
  </ContentPanel>
</template>
<style scoped>
.t-sample { min-width:56px;margin:0;background:var(--viewer-gray);border:1px solid var(--viewer-border);border-radius:6px; }
.sample-label.passed { color:var(--viewer-pass); }
.sample-label.failed { color:var(--viewer-fail); }
.sample-label.unknown { color:var(--viewer-muted); }
.sample-tests { display:flex;justify-content:center;align-items:center;min-width:0;height:16px;margin:0;padding:2px;font-size:10px;line-height:12px; }
.sample-tests > span:not(.pass-blocks) { overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }
.t-sample :deep(.p-panel-header) { flex-wrap:nowrap;align-items:center;gap:0;padding:2px; }
.t-sample :deep(.p-panel-header-actions) { flex-wrap:nowrap;flex-shrink:0;gap:0; }
.t-sample :deep(.panel-label) { flex:1;flex-wrap:nowrap;gap:2px;align-self:center; }
.t-sample :deep(.p-panel-content) { padding:0; }
</style>
