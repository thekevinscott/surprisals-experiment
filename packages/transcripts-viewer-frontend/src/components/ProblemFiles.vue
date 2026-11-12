<script setup>
import { openFile } from '../composables/filePreview.js'
const props = defineProps({ runId: String })
const files = ['question.txt', 'input_output.json', 'solutions.json']
const url = name => `/api/runs/${encodeURIComponent(props.runId)}/problem/${name}`
const viewer = name => `#files/${name}?${new URLSearchParams({src: url(name)})}`
</script>
<template>
  <nav class="problem-files" aria-label="Problem files">
    <span class="section-label">Files</span>
    <a v-for="name in files" :key="name" :href="viewer(name)" @click.prevent="openFile(viewer(name))">{{ name }}</a>
  </nav>
</template>
<style scoped>
.problem-files { display: flex; flex-direction: column; gap: 4px; font-size: 12px; }
.section-label { color: #657186; font-size: 10px; }
.problem-files a { text-decoration: none; }
.problem-files a:hover { text-decoration: underline; }
</style>
