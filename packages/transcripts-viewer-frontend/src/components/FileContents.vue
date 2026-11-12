<script setup>
import { ref, inject } from 'vue'
import { useLazyResource } from '../composables/api.js'
import { fileSize } from '../composables/fileSize.js'
import FileContent from './FileContent.vue'
import ContentPanel from './ContentPanel.vue'
const props = defineProps({ file: Object })
const rawSourceUrl = inject('rawSourceUrl', () => undefined)
const expanded = ref(false)
const {data:text,error}=useLazyResource(expanded,async signal=>{
  if(props.file.text != null)return props.file.text
  const response=await fetch(props.file.url ?? rawSourceUrl(props.file.source),{signal})
  if(!response.ok)throw Error(`HTTP ${response.status}`)
  return response.text()
})
</script>
<template>
  <ContentPanel :source="file.source" v-model:expanded="expanded" :title="`File · ${file.name}`" :summary="fileSize(file.bytes)" preview class="file-content">
    <p v-if="!expanded">{{ file.preview }}</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <p v-else-if="text === null">Loading file…</p>
    <FileContent v-else :name="file.name" :text="text" />
  </ContentPanel>
</template>
<style scoped>
.file-content { margin-top: 8px; }
p, .file-content :deep(p) { white-space: pre-wrap; overflow-wrap: anywhere; font-family: ui-monospace, monospace; font-size: 11px; }
</style>
