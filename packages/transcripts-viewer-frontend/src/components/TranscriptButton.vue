<script setup>
import {computed,inject,ref} from 'vue'
import Button from 'primevue/button'
import Popover from 'primevue/popover'
import {openTranscript} from '../composables/filePreview.js'
const props=defineProps({source:String,files:Array,modalTitle:String,turnMetadata:Object,label:{type:String,default:'Open transcript'}})
const rawUrl=inject('rawSourceUrl')
const sourceUrl=inject('sourceUrl')
const picker=ref(null)
const files=computed(()=>(props.source?[{source:props.source}]:(props.files??[])).map(file=>({...file,url:rawUrl(file.source)})))
function openFile(file) {
  picker.value?.hide()
  const title=props.modalTitle ?? (props.source?'U transcript':'Transcript')
  const hash=props.turnMetadata?.u_request_sha256
  openTranscript({name:hash ? `${title} · u_request_sha256: ${hash}` : title,files:files.value,sourceUrl,turnMetadata:props.turnMetadata,uView:!!props.source},file)
}
function open(event) {
  if(files.value.length===1)openFile(files.value[0])
  else picker.value.toggle(event)
}
</script>
<template>
  <Button class="icon-button" text size="small" :label="label" aria-label="Open transcript" title="Open transcript" :disabled="!files.length" @click="open" />
  <Popover ref="picker">
    <nav class="transcript-files" aria-label="Transcript files"><button v-for="file in files" :key="file.source" type="button" @click="openFile(file)">{{ file.source }}</button></nav>
  </Popover>
</template>
<style scoped>
.transcript-files { display:grid;max-width:min(640px,80vw);max-height:60vh;overflow:auto;gap:4px; }
.transcript-files button { border:0;border-radius:6px;background:var(--viewer-gray);padding:8px;text-align:left;overflow-wrap:anywhere;font-size:12px;color:inherit;cursor:pointer; }
</style>
