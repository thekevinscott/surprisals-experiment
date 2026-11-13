<script setup>
import { turnSummary } from '../composables/outcomes.js'
import { inject } from 'vue'
import TranscriptButton from './TranscriptButton.vue'
import ContentPanel from './ContentPanel.vue'
import Button from 'primevue/button'
import {openFile} from '../composables/filePreview.js'
import TTranscripts from './TTranscripts.vue'
const props=defineProps({ turn: Object })
const sourceUrl=inject('sourceUrl')
function openAdvice() {
  openFile(sourceUrl(props.turn.adviceSource),{initialText:props.turn.advice,tokens:props.turn.tokens,measurement:props.turn.measurement==null?'Measurement unavailable':`${props.turn.measurement} ${props.turn.unit}`})
}
const link = inject('runLink')
</script>
<template>
  <ContentPanel :collapsible="false" class="turn-block" :data-turn="turn.id" :title="`U · turn ${turn.id}`" :href="link(turn.source)" :metadata="{'metadata.json':turn.metadata,'advice.json':turn.adviceMetadata}">
    <template #summary><span>{{ turnSummary(turn) }}</span></template>
    <template #actions><Button class="icon-button" v-if="turn.advice != null" text size="small" label="💡" aria-label="Open advice" title="Open advice" @click="openAdvice" /><TranscriptButton :source="turn.transcriptPath" :turn-metadata="turn.metadata" label="💬" /></template>
    <p v-if="turn.error" class="turn-error" role="status">U failed: {{ turn.error }}</p>
    <TTranscripts :samples="turn.samples ?? []" />
  </ContentPanel>
</template>
<style scoped>
.turn-block { background: var(--viewer-gray); --p-panel-header-padding: 2px 4px; --p-panel-content-padding: 0 4px 4px; }
</style>
