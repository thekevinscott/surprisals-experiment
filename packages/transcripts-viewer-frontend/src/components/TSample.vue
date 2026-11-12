<script setup>
import { inject,computed } from 'vue'
import {fetchJson,useLiveResource} from '../composables/api.js'
import PassBlocks from './PassBlocks.vue'
import { attemptState, attemptOutcome } from '../composables/outcomes.js'
import ContentPanel from './ContentPanel.vue'
import TAttempt from './TAttempt.vue'
import TranscriptButton from './TranscriptButton.vue'
const props=defineProps({ sample: Object })
const apiUrl=inject('apiUrl')
const {data,loading,error}=useLiveResource(()=>[apiUrl(props.sample.source)],(signal,[url])=>fetchJson(url,signal))
const latest=computed(()=>data.value?.attempts.find(attempt=>attempt.id===props.sample.latest?.id) ?? props.sample.latest)
</script>
<template>
  <ContentPanel local :collapsible="false" class="t-sample" :data-sample="sample.id" :title="`T${sample.id}`">
    <template #title><span class="sample-label" :class="attemptOutcome(sample.latest)">T{{ sample.id }}</span></template>
    <template #actions><TranscriptButton v-if="data?.attempts.length" :files="data.attempts.flatMap(attempt => attempt.transcriptFiles ?? [])" label="💬" /></template>
    <div class="sample-tests">
      <PassBlocks v-if="latest?.tests && !latest.generation?.timed_out && !latest.generation?.error" :passed="latest.tests.passed" :total="latest.tests.total" :cases="latest.tests.cases" :source="latest.testsSource" />
      <span v-else>{{ attemptState(sample.latest) }}</span>
    </div>
    <div class="sample-scroll">
      <p v-if="loading">Loading attempts…</p><p v-else-if="error" role="alert">{{ error }}</p>
      <TAttempt v-for="attempt in (loading ? [] : data?.attempts ?? [])" :key="attempt.id" :attempt="attempt" :flat="data?.attempts.length === 1" />
    </div>
  </ContentPanel>
</template>
<style scoped>
.t-sample { min-width: 0; margin: 0; background: #f8fafc; border: 1px solid #d0dae7; border-radius: 6px; }
.sample-label.passed { color: #15803d; }
.sample-label.failed { color: #b91c1c; }
.sample-label.unknown { color: #657186; }
.sample-scroll { padding: 0 2px 2px; }
.sample-tests { display: flex; justify-content: center; align-items: center; min-width: 0; margin: 2px 0 4px; font-size: 10px; overflow-wrap: anywhere; }
.t-sample :deep(.p-panel-header) { flex-wrap: nowrap; align-items: flex-start; gap: 0; padding: 2px; }
.t-sample :deep(.p-panel-header-actions) { flex-wrap: nowrap; flex-shrink: 0; }
.t-sample :deep(.panel-label) { flex: 1; flex-wrap: nowrap; gap: 2px; align-self: center; }
.t-sample :deep(.p-panel-header .p-button) { padding: 2px; }
.t-sample :deep(.p-panel-toggle-button) { width: 18px; height: 18px; }
.t-sample :deep(.p-panel-content) { padding: 0 2px 2px; }
p { font-size: 11px; color: #657186; }
</style>
