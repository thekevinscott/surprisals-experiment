<script setup>
import { turnSummary } from '../composables/outcomes.js'
import { ref, inject } from 'vue'
import TranscriptButton from './TranscriptButton.vue'
import ContentPanel from './ContentPanel.vue'
import Button from 'primevue/button'
import {openFile} from '../composables/filePreview.js'
import TTranscripts from './TTranscripts.vue'
const props=defineProps({ turn: Object })
const sourceUrl=inject('sourceUrl')
function openAdvice() {
  openFile(sourceUrl(`${props.turn.source}/u/advice.txt`),{initialText:props.turn.advice,tokens:props.turn.tokens,measurement:props.turn.measurement==null?'Measurement unavailable':`${props.turn.measurement} ${props.turn.unit}`})
}
const expanded = ref(true)
const link = inject('runLink')
const apiUrl = inject('apiUrl')
</script>
<template>
  <ContentPanel v-model:expanded="expanded" class="turn-block" :data-turn="turn.id" :title="`U · turn ${turn.id}`" :href="link(turn.source)" :summary="turnSummary(turn)">
    <p v-if="turn.error" class="turn-error" role="status">U failed: {{ turn.error }}</p>
    <TranscriptButton v-if="!turn.error || turn.advice != null" :source="turn.transcriptPath" :url="apiUrl(`${turn.source}/transcript`)" />
    <Button v-if="turn.advice != null" text size="small" label="Open advice" @click="openAdvice" />

    <TTranscripts :samples="turn.samples ?? []" />
  </ContentPanel>
</template>
<style scoped>
.turn-block { background: #edf3fc; }
</style>
