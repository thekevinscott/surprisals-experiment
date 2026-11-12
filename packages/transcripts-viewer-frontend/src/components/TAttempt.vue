<script setup>
import { attemptState } from '../composables/outcomes.js'
import ContentPanel from './ContentPanel.vue'
import TranscriptButton from './TranscriptButton.vue'
import FileContents from './FileContents.vue'
import TestResults from './TestResults.vue'
defineProps({attempt:Object})
</script>
<template>
  <ContentPanel :title="`Attempt ${attempt.id}`" :summary="attemptState(attempt)" :expanded="true">
    <template #actions><TranscriptButton :files="attempt.transcriptFiles" label="💬" /></template>
    <FileContents v-for="file in attempt.files" :key="file.name" :file="file" />
    <p v-if="!attempt.files.length">No written files recorded</p>
    <TestResults :results="attempt.tests" :missing-reason="attemptState(attempt)" :source="attempt.testsSource" />
  </ContentPanel>
</template>
