<script setup>
import {inject} from 'vue'
import Button from 'primevue/button'
import {openTranscript} from '../composables/filePreview.js'
const props=defineProps({source:String,files:Array,modalTitle:String,label:{type:String,default:'Open transcript'}})
const rawUrl=inject('rawSourceUrl')
const sourceUrl=inject('sourceUrl')
function open() {
  const files=(props.source?[{source:props.source}]:(props.files??[])).map(file=>({...file,url:rawUrl(file.source)}))
  openTranscript({name:props.modalTitle ?? (props.source?'U transcript':'Transcript'),files,source:props.source,sourceUrl,
    rawFiles:props.source?[{source:props.source,url:rawUrl(props.source)}]:files})
}
</script>
<template>
  <Button class="icon-button" text size="small" :label="label" aria-label="Open transcript" title="Open transcript" :disabled="!source && !files?.length" @click="open" />
</template>
