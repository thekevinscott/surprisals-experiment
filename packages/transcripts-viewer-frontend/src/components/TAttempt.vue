<script setup>
import { attemptState } from '../composables/outcomes.js'
import ContentPanel from './ContentPanel.vue'
import TranscriptButton from './TranscriptButton.vue'
import FileContents from './FileContents.vue'
defineProps({attempt:Object,flat:Boolean})
</script>
<template>
  <div v-if="flat" class="attempt-files">
    <FileContents v-for="file in attempt.files" :key="file.name" :file="file" :icon-only="attempt.files.length === 1" />
    <p v-if="!attempt.files.length">No written files recorded</p>
  </div>
  <ContentPanel v-else :title="`Attempt ${attempt.id}`" :expanded="true" class="attempt-panel">
    <template #summary><span>{{ attemptState(attempt) }}</span></template>
    <template #actions><TranscriptButton :files="attempt.transcriptFiles" label="💬" /></template>
    <FileContents v-for="file in attempt.files" :key="file.name" :file="file" :icon-only="attempt.files.length === 1" />
    <p v-if="!attempt.files.length">No written files recorded</p>
  </ContentPanel>
</template>
<style scoped>
p { overflow-wrap: anywhere; font-size: 10px; }
.attempt-panel :deep(.p-panel-header) { flex-wrap: wrap; }
</style>
