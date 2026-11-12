<script setup>
import PassBlocks from './PassBlocks.vue'
import { attemptState } from '../composables/outcomes.js'
import ContentPanel from './ContentPanel.vue'
import TranscriptButton from './TranscriptButton.vue'
import FileContents from './FileContents.vue'
import TestResults from './TestResults.vue'
defineProps({attempt:Object})
</script>
<template>
  <ContentPanel :title="`Attempt ${attempt.id}`" :expanded="true">
    <template #summary>
      <PassBlocks v-if="attempt?.tests && !attempt.generation?.timed_out && !attempt.generation?.error" :passed="attempt.tests.passed" :total="attempt.tests.total" :cases="attempt.tests.cases" :source="attempt.testsSource" />
      <span v-else>{{ attemptState(attempt) }}</span>
    </template>
    <template #actions><TranscriptButton :files="attempt.transcriptFiles" label="💬" /></template>
    <FileContents v-for="file in attempt.files" :key="file.name" :file="file" />
    <p v-if="!attempt.files.length">No written files recorded</p>
    <TestResults :results="attempt.tests" :missing-reason="attemptState(attempt)" :source="attempt.testsSource" />
  </ContentPanel>
</template>
