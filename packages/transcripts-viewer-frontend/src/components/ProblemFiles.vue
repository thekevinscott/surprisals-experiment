<script setup>
import {fileLink} from '../router.js'
import { openFile } from '../composables/filePreview.js'
const props = defineProps({ runId: String })
const files = ['question.txt', 'input_output.json', 'solutions.json']
const url = name => `/api/runs/${encodeURIComponent(props.runId)}/problem/${name}`
const viewer = name => fileLink(url(name),name)
</script>
<template>
  <nav class="problem-files" aria-label="Problem files">
    <span class="section-label">Files</span>
    <div class="file-links"><a v-for="name in files" :key="name" :href="viewer(name)" @click.prevent="openFile(viewer(name))">{{ name }}</a></div>
  </nav>
</template>
<style scoped>
.problem-files { display: flex; flex-direction: column; gap: 4px; min-width:0; font-size: 12px; }
.section-label { color: var(--viewer-muted); font-size: 10px; }
.file-links { display:flex; flex-wrap:nowrap; gap:12px; max-width:100%; overflow-x:auto; }
.problem-files a { flex:none; white-space:nowrap; text-decoration: none; }
.problem-files a:hover { text-decoration: underline; }
</style>
