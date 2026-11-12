<script setup>
import { turnSummary } from '../composables/outcomes.js'
import { ref, inject } from 'vue'
import AsyncTranscript from './AsyncTranscript.vue'
import ContentPanel from './ContentPanel.vue'
import TextSection from './TextSection.vue'
import TTranscripts from './TTranscripts.vue'
defineProps({ turn: Object })
const expanded = ref(true)
const link = inject('runLink')
const apiUrl = inject('apiUrl')
</script>
<template>
  <ContentPanel v-model:expanded="expanded" class="turn-block" :data-turn="turn.id" :title="`U · turn ${turn.id}`" :href="link(turn.source)" :summary="turnSummary(turn)">
    <p v-if="turn.error" class="turn-error" role="status">U failed: {{ turn.error }}</p>
    <AsyncTranscript v-if="!turn.error || turn.advice != null" :source="turn.transcriptPath" :url="apiUrl(`${turn.source}/transcript`)" />
    <TextSection verbatim v-if="!turn.error || turn.advice != null" label="Advice" :source="`${turn.source}/u/advice.txt`" :text="turn.advice" :tokens="turn.tokens"
      :measurement="turn.measurement == null ? 'Measurement unavailable' : `${turn.measurement.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${turn.unit}`" />
    <TTranscripts :samples="turn.samples ?? []" />
  </ContentPanel>
</template>
<style scoped>
.turn-block { background: #edf3fc; }
</style>
