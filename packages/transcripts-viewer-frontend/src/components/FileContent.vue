<script setup>
import {computed} from 'vue'
import {matchFile} from '../composables/fileMatcher.js'
import TranscriptView from './TranscriptView.vue'
import {transcriptFile} from '../composables/transcriptFile.js'
import JsonContent from './JsonContent.vue'
import JsonlContent from './JsonlContent.vue'
import SolutionsContent from './SolutionsContent.vue'
const props=defineProps({name:String,text:String,line:String})
const kind=computed(()=>matchFile(props.name))
const messages=computed(()=>kind.value==='transcript'?transcriptFile(props.text,props.name):[])
</script>
<template>
  <TranscriptView v-if="kind==='transcript'" :messages="messages" :source="name" :initial-line="line" />
  <SolutionsContent v-else-if="kind==='solutions'" :text="text" />
  <JsonContent v-else-if="kind==='json'" :text="text" />
  <JsonlContent v-else-if="kind==='jsonl'" :text="text" :line="line" />
  <pre v-else>{{ text }}</pre>
</template>
<style scoped>
pre { margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font-family:ui-monospace,monospace;font-size:12px; }
</style>
