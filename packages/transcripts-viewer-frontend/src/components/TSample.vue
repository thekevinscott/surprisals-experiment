<script setup>
import { ref,inject } from 'vue'
import {fetchJson,useLiveResource} from '../composables/api.js'
import PassBlocks from './PassBlocks.vue'
import { attemptState, attemptOutcome } from '../composables/outcomes.js'
import ContentPanel from './ContentPanel.vue'
import TAttempt from './TAttempt.vue'
const props=defineProps({ sample: Object })
const expanded = ref(true)
const apiUrl=inject('apiUrl')
const {data,loading,error}=useLiveResource(()=>expanded.value?[apiUrl(props.sample.source)]:[],(signal,[url])=>fetchJson(url,signal))
</script>
<template>
  <ContentPanel local v-model:expanded="expanded" class="t-sample" :data-sample="sample.id" :title="`T${sample.id}`">
    <template #title><span class="sample-label" :class="attemptOutcome(sample.latest)">T{{ sample.id }}</span></template>
    <template #summary>
      <PassBlocks v-if="sample.latest?.tests && !sample.latest.generation?.timed_out && !sample.latest.generation?.error" :passed="sample.latest.tests.passed" :total="sample.latest.tests.total" />
      <span v-else>{{ attemptState(sample.latest) }}</span>
    </template>
    <div v-if="expanded" class="sample-scroll">
      <p v-if="loading">Loading attempts…</p><p v-else-if="error" role="alert">{{ error }}</p>
      <TAttempt v-for="attempt in (loading ? [] : data?.attempts ?? [])" :key="attempt.id" :attempt="attempt" />
    </div>
  </ContentPanel>
</template>
<style scoped>
.t-sample { min-width: 0; margin: 0; background: #f8fafc; border: 1px solid #d0dae7; border-radius: 6px; }
.sample-label.passed { color: #15803d; }
.sample-label.failed { color: #b91c1c; }
.sample-label.unknown { color: #657186; }
.sample-scroll { padding: 0 2px 2px; }
p { font-size: 11px; color: #657186; }
</style>
