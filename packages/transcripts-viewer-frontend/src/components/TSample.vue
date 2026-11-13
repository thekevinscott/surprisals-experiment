<script setup>
import { inject,computed } from 'vue'
import {fetchJson,useLiveResource} from '../composables/api.js'
import PassBlocks from './PassBlocks.vue'
import { attemptState, attemptOutcome, transcriptFailure } from '../composables/outcomes.js'
import ContentPanel from './ContentPanel.vue'
import Button from 'primevue/button'
import {sampleFiles} from '../composables/sampleFiles.js'
import {openFiles,openFile} from '../composables/filePreview.js'
import TranscriptButton from './TranscriptButton.vue'
const props=defineProps({ sample: Object })
const apiUrl=inject('apiUrl')
const rawUrl=inject('rawSourceUrl')
const sourceUrl=inject('sourceUrl')
const {data,loading,error}=useLiveResource(()=>[apiUrl(props.sample.source)],(signal,[url])=>fetchJson(url,signal))
const status=computed(()=>error.value || (loading.value?'Loading…':'Tests not recorded'))
const files=computed(()=>sampleFiles(data.value?.attempts ?? [],rawUrl))
</script>
<template>
  <ContentPanel local :collapsible="false" class="t-sample" :data-sample="sample.id" :title="`T${sample.id}`">
    <template #title><span class="sample-label" :class="attemptOutcome(sample.latest)">T{{ sample.id }}</span></template>
    <template #actions><Button class="icon-button" text size="small" aria-label="Open files" title="Open files" :disabled="!files.length" @click="openFiles({name:`T${sample.id} files`,files})"><svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m5 4-4 4 4 4m6-8 4 4-4 4M9.5 2l-3 12" /></svg></Button><TranscriptButton v-if="data?.attempts.length" :attempt-count="data.attempts.length" :files="data.attempts.flatMap(attempt => (attempt.transcriptFiles ?? []).map(file=>({...file,error:transcriptFailure(attempt),timedOut:!!attempt.generation?.timed_out})))" :modal-title="`T${sample.id} transcript`" label="💬" /></template>
    <div v-for="attempt in data?.attempts" :key="attempt.id" class="sample-attempt" :data-attempt="attempt.id">
      <div v-if="!attempt.generation?.timed_out || attempt.tests" class="sample-tests">
        <PassBlocks v-if="attempt.tests?.cases?.length" :passed="attempt.tests.passed" :total="attempt.tests.total" :cases="attempt.tests.cases" :source="attempt.testsSource" />
        <a v-else-if="attempt.tests" :href="sourceUrl(attempt.testsSource)" @click.prevent="openFile(sourceUrl(attempt.testsSource))">Tests</a>
        <span v-else :title="attemptState(attempt)">{{ attemptState(attempt) }}</span>
      </div>
    </div>
    <div v-if="!data?.attempts.length" class="sample-tests"><span :title="status">{{ status }}</span></div>
  </ContentPanel>
</template>
<style scoped>
.t-sample { min-width:56px;margin:0;background:var(--viewer-gray);border:1px solid var(--viewer-border);border-radius:6px; }
.sample-label.passed { color:var(--viewer-pass); }
.sample-label.failed { color:var(--viewer-fail); }
.sample-label.unknown { color:var(--viewer-muted); }
.sample-attempt + .sample-attempt { border-top:1px solid var(--viewer-border); }
.sample-tests { display:flex;justify-content:center;align-items:center;min-width:0;height:16px;margin:0;padding:2px;font-size:10px;line-height:12px; }
.sample-tests > span:not(.pass-blocks) { overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }
.t-sample :deep(.p-panel-header) { flex-wrap:nowrap;align-items:center;gap:0;padding:2px; }
.t-sample :deep(.p-panel-header-actions) { flex-wrap:nowrap;flex-shrink:0;gap:0; }
.t-sample :deep(.panel-label) { flex:1;flex-wrap:nowrap;gap:2px;align-self:center; }
.t-sample :deep(.p-panel-content) { padding:0; }
</style>
