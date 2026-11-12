<script setup>
import {transcriptContent,transcriptMetadata,transcriptReasoning} from '../composables/transcriptFile.js'
import TextSection from './TextSection.vue'
defineProps({label:String,message:Object,stateKey:String,contentOnly:Boolean})
</script>
<template>
  <TextSection verbatim :label="label" :state-key="stateKey" :source="contentOnly ? undefined : message.source" :source-line="message.line" :text="contentOnly ? transcriptContent(message.raw) : message.raw" :reasoning="contentOnly ? transcriptReasoning(message.raw) : undefined" :metadata="contentOnly ? transcriptMetadata(message.raw) : undefined" />
</template>
