<script setup>
import { inject } from 'vue'
import { useLiveResource,fetchText } from '../composables/api.js'
import { fileSize } from '../composables/fileSize.js'
import FileContent from './FileContent.vue'
import ContentPanel from './ContentPanel.vue'
const props = defineProps({ file: Object })
const rawSourceUrl = inject('rawSourceUrl', () => undefined)
const {data:text,error}=useLiveResource(
  ()=>[props.file.url ?? rawSourceUrl(props.file.source)],
  (signal,[url])=>fetchText(url,signal),
)
</script>
<template>
  <ContentPanel :source="file.source" :title="`File · ${file.name}`" :summary="fileSize(file.bytes)" :collapsible="false" class="file-content">
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="text === null">Loading file…</p>
    <FileContent v-else :name="file.name" :text="text" />
  </ContentPanel>
</template>
<style scoped>
.file-content { margin-top: 8px; }
p, .file-content :deep(p) { white-space: pre-wrap; overflow-wrap: anywhere; font-family: ui-monospace, monospace; font-size: 11px; }
</style>
